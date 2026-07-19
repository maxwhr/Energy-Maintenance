# Task 25B-R2 Pilot 切换与回滚报告

- 切换状态：BLOCKED_NO_PILOT_INDEX
- Pilot 路由激活：False
- 激活前阻断：True
- 普通用户未受影响：True
- 回滚状态：NOT_REQUIRED_ROUTE_NEVER_CHANGED
- Base 路由保持/恢复：True
- `.env` 默认配置变化：False
- 说明：真实 Pilot 索引未达到 300，安全门禁在路由改变前拒绝激活，因此没有伪造一次回滚成功。
