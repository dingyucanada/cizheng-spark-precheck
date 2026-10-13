"""Small, inspectable source index. Lexical retrieval is not semantic verification."""
import asyncio
import hashlib
import json
import re
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
import httpx

MET_API = "https://collectionapi.metmuseum.org/public/collection"
AIC_API = "https://api.artic.edu/api/v1/artworks/search"
SEARCH_TERMS = {"ceramics", "porcelain", "stoneware", "bowl", "vase", "jar", "dish", "celadon", "Longquan", "blue and white", "Jingdezhen", "Chinese"}


def tokens(value):
    value = value.lower()
    result = set(re.findall(r"[a-z0-9]+", value))
    for run in re.findall(r"[\u4e00-\u9fff]+", value):
        result.update(run[i:i+2] for i in range(len(run)-1))
    return result


def normalize_met(raw):
    identifier = int(raw["objectID"])
    fields = ["title", "objectName", "culture", "period", "dynasty", "objectDate", "medium", "dimensions", "accessionNumber"]
    excerpt = "\n".join(f"{k}: {str(raw.get(k, ''))[:450]}" for k in fields)
    return {
        "id": f"MET-{identifier}", "provider": "The Metropolitan Museum of Art", "source_group": "metmuseum",
        "object_id": identifier, "title": str(raw.get("title", "Untitled"))[:200],
        "url": f"https://www.metmuseum.org/art/collection/search/{identifier}",
        "excerpt": excerpt, "record_sha256": hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
        "public_domain": bool(raw.get("isPublicDomain")), "medium": str(raw.get("medium", "")),
        "public_record": True,
        "date": str(raw.get("objectDate", "")), "accession": str(raw.get("accessionNumber", "")),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "image_url": raw.get("primaryImageSmall", "") if raw.get("isPublicDomain") else "",
    }


def normalize_aic(raw):
    identifier = int(raw['id'])
    fields = ['title','artist_display','date_display','medium_display','dimensions','main_reference_number']
    image_id = raw.get('image_id') or ''
    image_safe = bool(re.fullmatch(r'[a-zA-Z0-9-]+', image_id))
    return {'id': f'AIC-{identifier}', 'provider': 'Art Institute of Chicago', 'source_group': 'artic',
            'title': str(raw.get('title') or 'Untitled')[:200], 'url': f'https://www.artic.edu/artworks/{identifier}',
            'excerpt': '\n'.join(f'{k}: {str(raw.get(k) or "")[:450]}' for k in fields),
            'record_sha256': hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
            'public_record': True, 'public_domain': raw.get('is_public_domain') is True,
            'medium': str(raw.get('medium_display') or ''), 'date': str(raw.get('date_display') or ''),
            'accession': str(raw.get('main_reference_number') or ''), 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'image_url': f'https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg' if image_safe and raw.get('is_public_domain') is True else ''}


class Knowledge:
    def __init__(self, root, cache):
        self.root, self.cache = Path(root), Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.refs = []
        for path in sorted((self.root / "records").glob("*.json")):
            raw = json.loads(path.read_text())
            ref = normalize_aic(raw) if path.name.startswith('AIC-') else normalize_met(raw)
            ref["retrieved_at"] = "2026-10-14T00:00:00+08:00" if path.name.startswith('AIC-') else "2026-10-11T00:00:00+08:00"
            self.refs.append(ref)
        self.photos = json.loads((self.root / "photos.json").read_text())
        for path in sorted((self.root / "curated").glob("*.json")):
            self.refs.append(json.loads(path.read_text()))
        for path in sorted(self.cache.glob("MET-*.json")):
            try:
                ref = normalize_met(json.loads(path.read_text()))
                if ref["id"] not in {x["id"] for x in self.refs}:
                    self.refs.append(ref)
            except (ValueError, KeyError):
                continue
        for path in sorted(self.cache.glob('AIC-*.json')):
            try:
                ref=normalize_aic(json.loads(path.read_text()))
                if ref['id'] not in {r['id'] for r in self.refs}:
                    self.refs.append(ref)
            except (ValueError, KeyError):
                continue

    def origins(self, photos):
        found = []
        for p in photos:
            for known in self.photos:
                kind = None
                if p["sha256"] == known["sha256"]:
                    kind = "exact_file"
                elif p["pixel_sha256"] == known["pixel_sha256"]:
                    kind = "exact_pixels"
                elif (int(p["dhash"], 16) ^ int(known["dhash"], 16)).bit_count() <= 3:
                    kind = "visual_candidate"
                if kind:
                    found.append({"photo_id": p["id"], "reference_id": f"MET-{known['object_id']}",
                                  "match": kind, "source_photo": known["file"],
                                  "source_url": known["url"], "identity_verified": False})
        return found

    def get(self, identifier):
        return next((r for r in self.refs if r["id"] == identifier), None)

    def search(self, query, preferred=(), limit=5):
        query_tokens = tokens(query)
        ranked = []
        for ref in self.refs:
            match = len(query_tokens & tokens(ref["excerpt"] + " " + ref.get("keywords", "")))
            score = match + (50 if ref["id"] in preferred else 0)
            if score:
                ranked.append((score, ref))
        return [dict(ref, retrieval_score=score) for score, ref in sorted(ranked, key=lambda x: -x[0])[:limit]]

    async def _met_search(self, terms):
        # Terms originate from a closed enum in ObservationSet, not free-form user text.
        query = " ".join(x for x in terms[:4] if x in SEARCH_TERMS)
        if not query:
            return [], {"status": "skipped", "reason": "没有可公开的检索词"}
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
            try:
                r = await client.get(MET_API + "/v1.1/search", params={"q": query, "hasImages": "true", "departmentId": 6, "limit": 4})
                r.raise_for_status()
                payload = r.json()
                ids = payload.get("objectIDs") or []
                async def fetch(identifier):
                    if not isinstance(identifier, int):
                        return None
                    result = await client.get(MET_API + f"/v1/objects/{identifier}")
                    result.raise_for_status()
                    raw = result.json()
                    if int(raw["objectID"]) != identifier:
                        return None
                    ref = normalize_met(raw)
                    self.cache.joinpath(ref["id"] + ".json").write_text(json.dumps(raw, ensure_ascii=False))
                    return ref
                results = await asyncio.gather(*(fetch(i) for i in ids[:4]), return_exceptions=True)
                refs = [r for r in results if isinstance(r, dict)]
                for ref in refs:
                    if ref['id'] not in {x['id'] for x in self.refs}:
                        self.refs.append(ref)
                return refs, {"status": "ok", "query": query, "count": len(refs), "provider": "The Met", "outbound": "受控器物词，不含照片及用户说明"}
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                return [], {"status": "unavailable", "provider": "The Met", "query": query, "http_status": exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None, "reason": "在线来源暂不可用，继续使用其他来源及本地资料"}

    async def _aic_search(self, terms):
        query = ' '.join(x for x in terms[:4] if x in SEARCH_TERMS)
        if not query:
            return [], {'status':'skipped','provider':'AIC'}
        # A generic "Chinese" OR-query overwhelms kiln/technique terms in this API.
        # Prefer a specific controlled keyword, then evaluate returned records separately.
        query = next((x for x in ('Longquan','Jingdezhen','blue and white') if x in terms), query)
        fields = 'id,title,artist_display,date_display,medium_display,dimensions,main_reference_number,is_public_domain,image_id'
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
            try:
                r = await client.get(AIC_API, params={'q':query,'limit':3,'fields':fields,'query[term][is_public_domain]':'true'})
                r.raise_for_status()
                refs=[]
                for raw in r.json().get('data',[])[:3]:
                    ref=normalize_aic(raw)
                    if not any(w in ref['medium'].lower() for w in ('porcelain','stoneware','ceramic','earthenware')):
                        continue
                    self.cache.joinpath(ref['id']+'.json').write_text(json.dumps(raw,ensure_ascii=False))
                    refs.append(ref)
                return refs, {'status':'ok','provider':'Art Institute of Chicago','query':query,'count':len(refs)}
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                return [], {'status':'unavailable','provider':'Art Institute of Chicago','query':query,'http_status':exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None,'reason':'在线来源暂不可用'}

    async def online_search(self, terms):
        results = await asyncio.gather(self._met_search(terms), self._aic_search(terms))
        refs = [ref for batch,_ in results for ref in batch]
        for ref in refs:
            if ref['id'] not in {x['id'] for x in self.refs}:
                self.refs.append(ref)
        return refs, {'status':'ok' if any(s['status']=='ok' for _,s in results) else 'unavailable',
                      'count':len(refs),'providers':[s for _,s in results], 'outbound':'仅受控器物词，不含照片及用户说明'}

    async def reference_images(self, refs, online=False):
        """At most two actual, licensed reference images. Never fetch model-supplied URLs."""
        from .imaging import inspect_photo
        result = []
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
            for ref in refs[:2]:
                seeded_image = self.root / 'reference-images' / (ref['id']+'.jpg')
                if seeded_image.is_file():
                    result.append((ref['id'],seeded_image)); continue
                known = next((p for p in self.photos if 'MET-'+str(p['object_id']) == ref['id']), None)
                if known:
                    original = self.root / known['file']
                    dest = self.cache / (ref['id']+'.jpg')
                    if not dest.exists():
                        _, preview = inspect_photo(original.read_bytes(), 'P1')
                        dest.write_bytes(preview)
                    result.append((ref['id'], dest))
                    continue
                dest = self.cache / (ref['id']+'.jpg')
                if dest.exists():
                    result.append((ref['id'], dest)); continue
                image_url = ref.get('image_url', '')
                u = urlparse(image_url)
                if not online or not ref.get('public_domain') or u.scheme != 'https' or u.hostname not in ('images.metmuseum.org','www.artic.edu') or u.username or u.password:
                    continue
                try:
                    data = bytearray()
                    async with client.stream('GET', image_url) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 6*1024*1024:
                                raise ValueError('reference image too large')
                    _, preview = inspect_photo(bytes(data), 'P1')
                    dest.write_bytes(preview)
                    result.append((ref['id'], dest))
                except (httpx.HTTPError, ValueError, OSError):
                    continue
        return result


def validate_comparisons(comparisons, observations, refs):
    """Reject invented sources, orphan observations and non-verbatim evidence quotes."""
    obs = {o["id"]: o for o in observations}
    source = {r["id"]: r for r in refs}
    accepted, rejected = [], []
    seen = set()
    for item in comparisons:
        reason = None
        if item["id"] in seen:
            reason = "duplicate_id"
        elif item["reference_id"] not in source:
            reason = "unknown_reference"
        elif any(i not in obs for i in item["observation_ids"]):
            reason = "unknown_observation"
        elif item["quote"] not in source[item["reference_id"]]["excerpt"]:
            reason = "quote_not_found"
        elif item['claim_relevance'] == 'direct' and source[item['reference_id']].get('applicability') == 'context_only':
            reason = 'reference_not_comparable'
        seen.add(item["id"])
        if reason:
            rejected.append({"comparison_id": item["id"], "reason": reason})
        else:
            accepted.append(dict(item, citation_verified=True, semantic_verified=False))
    return accepted, rejected
