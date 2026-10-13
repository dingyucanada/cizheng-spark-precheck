"""Public-photo scenarios. Claims are explicit exercise inputs, never altered museum records."""
EXAMPLES = {
    48450: dict(name='龙泉青釉修补碗', theme='修补复核', description='馆方记载金漆修补，重点核查修复状态',
                claim='核验口沿修补状态，是否需要进一步检查。', scenario='repair',
                roles=['overall','mouth','base'], premise='修补问题来自馆方记录。'),
    48607: dict(name='青花山水觚', theme='常规核验', description='核对康熙早期归属，形成常规核验意见',
                claim='资料说明为清代康熙早期青花山水觚，请核对这一说法。', scenario='catalog_consistent',
                roles=['overall','detail','base'], premise='归属说法取自馆方记录，不是对另一件实物的认证。'),
    51185: dict(name='几何纹彩绘茶壶', theme='年代说法冲突', description='体验设定“明代”，对照馆方19世纪记录',
                claim='体验设定：有人称这组照片对应明代茶壶，请核验年代说法。', scenario='claim_conflict',
                roles=['overall','detail','base'], premise='“明代”是本案例人为设置的待核验说法；真实馆藏记录为19世纪。'),
}
