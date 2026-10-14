"""Operator checks are separate from the collector's application."""
import hashlib
from .pdf_report import fonts


def readiness_snapshot(store, knowledge, settings, health, boot_time):
    checks = []
    def check(key, label, ok, detail):
        checks.append(dict(key=key, label=label, ok=bool(ok), detail=detail))
    check('model', '本地模型服务', health.get('ready'), health.get('message', '未连接'))
    try:
        fonts(); font_ok = True
    except Exception:
        font_ok = False
    check('font', '中文报告字体', font_ok, '可生成中文PDF' if font_ok else '需安装中文字体')
    try:
        intact = bool(knowledge.photos) and all(hashlib.sha256((settings.knowledge_dir/p['file']).read_bytes()).hexdigest()==p['sha256'] for p in knowledge.photos)
    except OSError:
        intact = False
    check('photos', '排练照片完整性', intact, f'{len(knowledge.photos)} 张公开实物照片，核对原文件指纹')
    check('sources', '离线参考资料', bool(knowledge.refs), f'{len(knowledge.refs)} 条资料已载入')
    jobs = store.listing('job', 10000)
    backups = []
    for j in jobs:
        if j['status'] != 'complete' or j['mode'] != 'analyze':
            continue
        calls = j.get('model_calls', [])
        observed = any(c.get('purpose')=='observe' and c.get('status')=='ok' and c.get('location')=='local'
                       and c.get('model')==settings.model and c.get('image_count', 0)>=2 for c in calls)
        if not observed:
            continue
        try:
            r = store.get(j['id']+'_report', 'report')
            pdf = store.case_dir(r['case_id'])/(j['id']+'.pdf')
            valid = r.get('model_executed') is True and hashlib.sha256(pdf.read_bytes()).hexdigest()==r['pdf_sha256']
            valid = valid and all(hashlib.sha256((store.case_dir(r['case_id'])/p['original_file']).read_bytes()).hexdigest()==p['sha256'] for p in r['photos'])
        except (KeyError, OSError):
            continue
        if valid:
            backups.append(dict(job_id=j['id'], name=r['object_name'], generated_at=r['generated_at'],
                seconds=j.get('seconds'), current_session=j['created_at']>=boot_time,
                url='/?report='+j['id'], pdf_url='/api/jobs/'+j['id']+'/report.pdf'))
    fresh = any(b['current_session'] for b in backups)
    check('rehearsal', '本次启动后的完整视觉排练', fresh, '真实图片调用及报告已完成' if fresh else '请先完成一次真实图片预检；只连通服务不能代替排练')
    active = sum(j['status'] in ('queued', 'running') for j in jobs)
    check('idle', '当前任务队列', active==0, f'{active} 件正在排队或处理')
    return dict(ready=all(c['ok'] for c in checks), checks=checks, model=health.get('model'),
                backups=backups[:10], boot_time=boot_time,
                meaning='表示当前工程条件通过；演示耗时、投屏效果和专业观察仍需现场确认。')
