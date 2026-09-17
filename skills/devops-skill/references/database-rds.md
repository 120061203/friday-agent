# PostgreSQL / RDS — 環境慣例

## 背景
曾處理過的 RDS 實例:CAMT_V2_PROD、LEGALIQ_PLUS_PROD、WENZO_COPILOT_PROD、DCCS_DEV/PROD、lineworks_bot_service 等,常見任務是角色建立、ownership 轉移、default privileges 設定、readonly 帳號設定(在 DBeaver 操作)。

## Prod 資料模擬到 Staging(不影響 Prod 運行的做法)

不要直接對 Prod RDS 跑 `pg_dump`,標準流程:

**Phase 1 — 建立 Snapshot(避免影響 Prod)**
1. AWS Console → RDS → 對 Prod RDS 手動建立 Snapshot
2. 等待狀態變為 `available`
3. 從 Snapshot Restore 一個**臨時 RDS instance**(獨立於 Prod,不共用連線資源)

**Phase 2 — pg_dump(對臨時 instance 操作,不動 Prod)**
```bash
pg_dump \
  -h <temp-rds-host> \
  -U <username> \
  -d <database_name> \
  -F c \
  -f prod_snapshot_$(date +%Y%m%d).dump
```

**Phase 3 — 匯入 Staging**
```bash
pg_restore \
  -h <staging-rds-host> \
  -U <username> \
  -d <database_name> \
  -F c \
  prod_snapshot_$(date +%Y%m%d).dump
```

匯入後記得後續手動 mark 掉敏感資訊(這是既有的處理習慣,不是自動化步驟)。

## 角色/權限管理慣例

常見任務組合(依專案套用):
- Role 建立
- Ownership 轉移(把既有物件的 owner 改成新角色)
- Default privileges 設定(確保未來新建的 table/sequence 也套用同樣權限,不用每次手動 grant)
- Readonly 帳號設定(給唯讀查詢用途,常搭配 DBeaver 操作介面)

回答這類問題時,優先確認是哪一個 RDS 實例、哪個 database、目的是 CRUD 還是純 readonly,再給對應的 `CREATE ROLE`/`GRANT`/`ALTER DEFAULT PRIVILEGES` 語句,不用每次從頭解釋 PostgreSQL 權限模型的基礎概念。
