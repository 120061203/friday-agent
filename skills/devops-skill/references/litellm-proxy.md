# LiteLLM Proxy — 環境慣例

## 現況背景(多套並存,回答前務必先確認使用者問的是哪一套)

- **AWS 版本**:EC2 (m7i.xlarge/large) 後面掛 ALB,曾發現過 target group 重複註冊、殘留未使用 ALB(從舊遷移留下的)等清理型問題
- **Zeabur 版本**:PostgreSQL backing,Cloudflare DNS(orange-cloud proxy,SSL Flexible 模式解決過 502),整合 Open WebUI
- 兩套版本的 Virtual Key、model 設定不共通,曾有自訂 `claude_skill` provider(舊版 v1.82.3)需要遷移到新 Zeabur instance 的情境

## 常見問題模式與排查順序

**Domain/ALB 綁定問題**:
1. 先確認 domain 實際 CNAME/A record 指向哪個 ALB(`dig +short`)
2. 確認 ALB → target group → EC2 instance 的對應關係(不同 domain 可能各自對應完全不同的 ALB/EC2,別假設只有一套)
3. 檢查 target group 有沒有重複註冊同一台 EC2(曾發生過一台 EC2 同時在兩個 target group)
4. CloudWatch `RequestCount` 可以用來判斷某個 ALB/target group 是否為殘留無用資源(14 天內零流量基本可判定廢棄)
5. 清理順序建議:先 soft-disable listener → 確認 Route 53 無引用 → 刪 ALB → 刪 target group → 刪相關閒置 EC2

**docker-compose / Prometheus 設定**:
- 常見坑:`prometheus.yml` 被誤刪或變成資料夾(要注意 `rmdir`/`mkdir` 誤用),需要重新用 heredoc 寫回:
  ```bash
  cat > prometheus.yml << 'EOF'
  global:
    scrape_interval: 15s
    evaluation_interval: 15s
  scrape_configs:
    - job_name: 'litellm'
      static_configs:
        - targets: ['litellm:4000']
      metrics_path: '/metrics'
  EOF
  ```
- 啟動後驗證三個 container 都正常(litellm/prometheus/postgres),確認 Prometheus targets、確認關鍵環境變數(如 `PROXY_BASE_URL`)有生效
- local/RDS 兩種 docker-compose 檔案容易搞混用錯版本,若使用者提到「怎麼跑起來怪怪的」先確認是不是套錯 compose 檔

**FortiGate SSL Inspection 導致連線失敗(辦公室連不上,個人連得上這類問題)**:
- 排查順序:DNS 解析一致性 → WAF IP allowlist → EC2 security group → ALB security group → 都排除後才輪到 TLS/ALPN 層
- 關鍵診斷技巧:用 `openssl s_client` 測試,**不加 `-alpn` 成功但加 `-alpn h2,http/1.1` 就 connection reset**,這是 FortiGate Full SSL Inspection(`deep-inspection` profile)誤判 ALPN extension 的典型徵兆
- 解法:內建 `deep-inspection` profile 是唯讀的,GUI 修改不會生效,需要 clone 出一個 custom profile(或直接用 CLI 建立),加 `ssl-exempt` FQDN 例外,再更新對應 Firewall Policy 套用新 profile

**新增 model 是否需要更新 image**:
- 只是對「既有支援的 provider」加 model → 改 `config.yaml` 就好,不用換 image
- 新增「原本不支援的 provider」或 API 格式有變 → 才需要拉新版 image

## 面對這類問題的回答習慣
LiteLLM 相關問題常牽涉多層基礎設施(DNS → ALB → SG → EC2 → 應用層設定),回答時建議按圖層順序逐一排除,而不是直接跳到假設性的猜測;習慣自己動手用 `dig`/`curl`/`openssl s_client`/AWS CLI 交叉驗證,可以直接給對應指令而不用先解釋工具是什麼。
