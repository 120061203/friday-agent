# HashiCorp Vault — 環境慣例

## 現況背景
- 目前版本:v2.0.3
- Unseal 方式:AWS KMS auto-unseal + Shamir recovery seals
- Storage backend:Raft
- 進行中的遷移:舊 Vault 網域 → 新 Vault 網域

## 換網域 vs 重建 Vault(關鍵區分)

**只是換網域(資料要保留)**:不需要重建,照下面步驟改設定就好:
1. DNS:在新網域加 A/CNAME,先跟舊的並存,別急著砍舊的
2. TLS 憑證:簽發涵蓋新網域的憑證(可用 SAN 把兩個網域包進同一張,過渡期方便)
3. `config.hcl`:
   - listener 的 `cert_file`/`key_file` 確認換新憑證
   - `api_addr` 改成 `https://vault.新網域:8200`
   - 多節點 Raft cluster 要同時檢查 `cluster_addr`
   - 改 `api_addr`/`cluster_addr` 通常需要重啟服務(只換憑證檔案內容不用重啟)
4. 反向代理(nginx/Caddy):server_name/host 規則加新網域
5. **檢查所有寫死舊網域的客戶端**(最容易漏掉的一步):
   - Bitbucket Pipelines 環境變數/secrets(`VAULT_ADDR`)
   - ArgoCD 的 Vault plugin 設定
   - AppRole 相關 script / CI 設定
   - LiteLLM 的 Vault 整合設定
   - 本機 `.bashrc`/`.env` 的 `VAULT_ADDR`
   - Vault Agent 設定(auto-unseal 或 token renew 用途)
6. 測試:`VAULT_ADDR=https://vault.新網域:8200 vault status`
7. 確認新網域穩定運作一段時間後,再移除舊 DNS record、吊銷舊憑證

**真的要重建(全新 instance,舊資料不會自動帶過去,unseal keys/root token 要重新生成)**:
- 動機通常是:升級版本、換 storage backend(如 file → Raft/Consul)、環境髒了想乾淨重來
- 流程:
  1. **資料遷移規劃**:盤點 KV v2 secrets、PKI CA、AppRole role_id/secret_id、Policy(HCL 檔通常有備份可重新 apply)
  2. 若原本就是 Raft,直接用 snapshot 最省事:
     ```bash
     vault operator raft snapshot save backup.snap
     # 新機器
     vault operator raft snapshot restore backup.snap
     ```
     前提是新舊都用 Raft 且版本相容
  3. 新機器部署:新 `config.hcl`(storage backend/listener/api_addr 用新網域),`vault operator init` 產生新的 unseal keys + root token(要重新妥善保存),unseal
  4. 還原資料:snapshot restore,或逐一搬 KV;PKI CA 若要保留同一條信任鏈,要把舊的 root/intermediate CA 憑證與私鑰匯出匯入(做錯會讓既有已簽發憑證失效)
  5. 重建 Policy 與 Auth 方法:AppRole、KV v2 mount、policy 都要重新設定 → **這是為什麼平常建議用 IaC(Terraform/HCL)管理 Vault 設定,重建時可以直接 replay**
  6. 更新所有客戶端的 `VAULT_ADDR`/token/AppRole 憑證(root token 換了,任何寫死舊 token 的地方都要更新)
  7. 確認新的穩定後再除役舊的

## Vault 升級注意事項(以 1.21.1 → 2.0.3 為例的踩坑紀錄)
大版本升級(如 1.x → 2.0)的 commit 列表很難看出重點,務必查官方 CHANGELOG.md / Upgrade Guide,重點檢查方向:
- **容器 `cap_ipc_lock`/`disable_mlock`**:2.0.2+ 若用容器/EKS 部署,務必檢查 `disable_mlock` 設定,否則可能啟動失敗或記憶體未鎖定寫入 swap
- **ACL policy 行為變更**:trailing-slash LIST 請求繞過 deny policy 的漏洞在後續版本被修復,若舊 policy 依賴這個舊行為(deny 被繞過才能運作),升級後可能被正確 deny,要先檢查
- **Raft 設定**:部分版本會拒絕 `performance_multiplier` ≤ 0 的設定值
- **Seal/KMS(AWS KMS auto-unseal + Shamir recovery 的情境)**:通常沒有破壞性變更,但 Seal HA 允許新節點加入已設定 Seal HA 的 cluster 這類功能可留意
- 建議升級路徑:先升到目前分支最新版確認相容性 → 測試環境驗證容器 capability 設定 → 檢查 ACL policy → 檢查 Raft 設定 → 才正式升級

## Policy 撰寫慣例

命名/路徑慣例是 `kv-{service}-{env}` 或 `kv_{service}_{env}`(依既有專案命名為準,不要自創新格式),KV v2 需要 `data/` 和 `metadata/` 前綴。

**標準 CRUD policy 模板(KV v2)**:
```hcl
# 讓 user 能在 kv-{service}-{env} 內 CRUD secret(KV v2 的 data endpoint)
path "kv-{service}-{env}/data/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# 列出 kv-{service}-{env} 資料夾
path "kv-{service}-{env}/metadata/" {
  capabilities = ["list"]
}
```

**唯讀 policy 模板**:
```hcl
path "kv-{service}-{env}/*" {
  capabilities = ["read", "list"]
}
path "kv-{service}-{env}/" {
  capabilities = ["list"]
}
```

寫入指令:
```bash
vault policy write {service}-{env} {service}-{env}-policy.hcl
```

同一服務常需要一次產出 local/staging/prod 三份,依樣畫葫蘆即可(env 換掉就好,格式維持一致)。

## 常見追問模式
使用者常會先給一個現有 policy 範例要求「照這個格式模仿」,這時**優先詢問 KV secret engine 的實際名稱**(不要用猜的),再套用既有格式產出。若使用者說「local/staging/prod 依樣畫葫蘆」,直接一次產出三個環境版本 + 對應的 `vault policy write` 指令。
