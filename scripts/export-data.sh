#!/bin/bash
# 导出当前数据库数据，供 Docker 部署使用
set -e

echo "=== 导出数据库结构 + 数据 ==="
mysqldump -u jckchen -p123 \
  --no-create-db \
  --complete-insert \
  stock_market \
  stocks daily_prices technical_indicators trading_calendar \
  > "$(dirname "$0")/stock_data.sql"

echo "✅ 导出完成: $(wc -c < "$(dirname "$0")/stock_data.sql") bytes"
