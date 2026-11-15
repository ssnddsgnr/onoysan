**Timestamp**: 2026-10-03 10:39:37

**User**: Сформулируйте yaml контрактом -- как у нас утроена тотальная инкапсуляция и отказоустойчивость -- со сторонними API, детали внутри системы, пайплайн взаимодействия и так далее.

**Gemini**:

```
# Контракт тотальной инкапсуляции и отказоустойчивости Sana FinOS[cite: 1, 2, 18]
version: "2026.1"[cite: 1, 2]
system: "Sana Backend Architecture (sana-core & Satellites)"[cite: 2, 8, 9]

encapsulation_and_isolation:
  identity_split:
    description: "Радикальный разрыв связи между социальной личностью и финансовым ядром"[cite: 20, 21, 22, 24]
    public_auth_layer:
      tables: ["auth.auth_identities", "auth.users_metadata"][cite: 20, 32, 53]
      data_stored: "Внешние ID (Telegram ID, Email) в зашифрованном виде (Encryption at Rest) и Argon2-хэши"[cite: 20, 21, 32]
      isolation: "Физически изолирован от финансовой схемы ledger; прямое объединение (JOIN) запрещено"[cite: 20, 32]
    private_core_layer:
      data_stored: "Исключительно анонимный internal_user_id (UUID)"[cite: 20, 21, 22]
      isolation: "В таблицах транзакций и кошельков отсутствуют поля имен, телефонов или email"[cite: 8, 21, 22]
    sanitary_gateway:
      action: "Identity Injection"[cite: 2, 6, 8, 9, 14, 20, 22, 24, 28, 33, 42]
      mechanism: "Подмена внешнего ID на анонимный UUID в оперативной памяти до передачи запроса в бизнес-логику"[cite: 2, 6, 8, 14, 22, 24]

  air_gap_policy:
    fiat_banking:
      direct_integrations: false[cite: 2, 8, 15, 22, 29, 43]
      disabled_providers: ["Plaid", "SaltEdge", "Прямые банковские API"][cite: 2, 8, 15, 22, 29, 43]
      ingestion_mode: "Human Bridge (MVA): фото чеков, скриншоты, текст, голосовые выписки"[cite: 8, 15, 29]
      benefit: "Исключает вектор атаки на банковские ключи и защищает данные при сбоях банков"[cite: 15, 22, 29]

  external_adapters_factory:
    pattern: "Provider Agnostic (Rust Traits + Runtime Factory)"[cite: 1, 3, 5, 8, 10]
    secret_management:
      strategy: "Secretless Code"[cite: 12, 34]
      source: "HashiCorp Vault / K8s Secrets"[cite: 1, 3, 5, 12, 16, 34]
      injection: "Инъекция в память процесса sana-core при старте без сохранения в коде или Docker-образе"[cite: 1, 3, 5, 12, 16, 34]
    adapters:
      ai_cognitive:
        trait: "ModelProvider"[cite: 1, 3, 5, 8, 10]
        implementations: ["GeminiFlashAdapter", "ClaudeOpusAdapter", "GroqAdapter"][cite: 1, 3, 5, 10]
        loop_strategy:
          fast_loop: "Groq / Gemini Flash — быстрая нормализация чеков и трат (<500ms)"[cite: 5, 10, 26]
          slow_loop: "Claude Opus / Gemini Pro — глубокий анализ и эмпатия Sana Zen / Nostradamus"[cite: 5, 10, 26]
      blockchain_gateway:
        trait: "ChainInformer"[cite: 1, 5, 10]
        implementations: ["InfuraAdapter", "AlchemyAdapter", "SelfHostedNodeAdapter"][cite: 1, 3, 5]
        consensus: "Round-Robin ротация и проверка консенсуса block_hash между провайдерами"[cite: 1, 3, 5]
      fx_market_data:
        trait: "ExchangeRateProvider"[cite: 3]
        implementations: ["BinanceAdapter", "CoinGeckoAdapter", "FixerAdapter"][cite: 3, 4, 32]
        fair_price_algorithm: "Взвешенное среднее с выкидыванием аномалий (Minute-Precision FX)"[cite: 3, 4, 10, 32]
      notification_gateway:
        trait: "NotificationSender"[cite: 5]
        implementations: ["EmailAdapter", "TelegramPushAdapter", "SystemBroadcastAdapter"][cite: 1, 5]

  data_sanitization_and_privacy:
    llm_sanitizer: "Удаление PII (телефоны, email, имена) из Context Payload перед отправкой во внешние LLM"[cite: 1, 3, 5, 10, 22, 24, 39]
    log_scrubbing: "Custom tracing-subscriber маскирует сырой текст в stdout/Loki на [REDACTED]"[cite: 6, 8, 12, 14]
    zero_persistence:
      media_storage: "RAM-only обработка или транзитный S3-буфер с коротких TTL (10 минут)"[cite: 2, 6, 12, 17, 18, 22, 24, 33]
      lifecycle: "Мгновенное уничтожение исходных фото чеков/аудио сразу после извлечения JSON"[cite: 2, 6, 12, 17, 18, 22, 24, 33]

fault_tolerance_and_resilience:
  constellation_topology:
    master_process:
      binary: "sana-core"[cite: 2, 8, 9, 14]
      role: "Stateless Orchestrator (Rust Tokio/Axum/Tonic)"[cite: 2, 8, 9, 14]
      error_handling: "Строгое использование Result<T, E>; использование panic! запрещено"[cite: 2, 6, 7, 14]
    satellites:
      ipc_protocol: "gRPC over Unix Domain Sockets (UDS) / internal TCP"[cite: 2, 4, 8, 9, 11]
      isolation_principle: "Panic & Memory Isolation (изолированные бинарники в отдельных процессах)"[cite: 4, 8, 9, 11, 16]
      registry:
        - name: "sana-nostradamus"
          role: "Предиктивный движок и расчет кассовых разрывов (Монте-Карло)"[cite: 2, 4, 8, 9, 18]
        - name: "sana-crypto-sync"
          role: "Stateless сканер блокчейнов (Read-Only)"[cite: 2, 4, 8, 9, 18]
        - name: "sana-fx-engine"
          role: "In-memory кэш курсов валют минутной точности"[cite: 2, 4, 8, 9, 18]
        - name: "sana-report-worker"
          role: "Генератор тяжелых PDF/Excel выгрузок через RabbitMQ"[cite: 2, 4, 8, 9, 18]
        - name: "sana-tax-worker"
          role: "Сложные налоговые расчеты юрисдикций"[cite: 2, 4, 9]
        - name: "sana-import-worker"
          role: "Парсинг и группировка исторических выписок (import_batches)"[cite: 4, 8]
      watchdog: "sana-core мониторит спутники и мгновенно перезапускает их при падении без блокировки API"[cite: 2, 4, 9, 11, 34]

  resilience_mechanisms:
    circuit_breaker:
      trigger: "Ошибки 5xx или таймауты внешних API"[cite: 1, 5, 8, 9]
      action: "Размыкание цепи, временно приостанавливающее вызовы к падающему вендору и переключающее на резерв"[cite: 1, 3, 5, 8, 9]
    retry_policy: "Экспоненциальная задержка до 3 повторных попыток"[cite: 4]
    dead_letter_queue:
      queue: "RabbitMQ / NATS DLQ"[cite: 4, 11, 12, 34]
      purpose: "Изоляция невалидных интентов и нечитаемых файлов без остановки конвейера"[cite: 4, 11, 12, 34]

  infrastructure_fortress:
    k8s_runtime: "Distroless Docker-образы без shell с жесткими CPU/RAM Resource Quotas"[cite: 12, 16]
    network_zones:
      zone_1_public: "Cloudflare WAF + ALB (прием зашифрованного HTTPS-трафика)"[cite: 2, 9, 12, 16, 18]
      zone_2_private_backend: "sana-core + Satellites + Conductor (gRPC mTLS, нет прямого входа из интернет)"[cite: 2, 9, 12, 16, 18]
      zone_3_private_data: "PostgreSQL + Redis + RabbitMQ (полная отрезка от интернета, доступ только у Core)"[cite: 2, 9, 12, 16, 18]

interaction_pipeline:
  dual_loop_flow:
    ingestion_loop:
      1_capture: "Вход сообщения/медиа от пользователя через WAF на Sanitary Gateway"[cite: 2, 6, 8, 17, 18, 28, 35]
      2_identity_and_sanitize: "Инъекция internal_user_id и маскирование PII в логах"[cite: 2, 6, 8, 14, 18, 28, 35]
      3_orchestration: "Входящий Дирижёр выбирает Агента и формирует Data Requirement Manifest"[cite: 2, 10, 17, 18, 28, 35]
      4_lazy_enrichment: "sana-core подгружает из БД/Redis только запрошенный короткий контекст"[cite: 2, 6, 8, 9, 10, 14, 17, 18, 28, 35]
      5_normalization: "Input Agent (Parser) декомпозирует сообщение в атомарные JSON-интенты"[cite: 8, 17, 18, 25, 28, 35]
      6_validation: "Intent Validator строгим типом проверяет JSON перед транзакцией"[cite: 2, 7, 8, 9, 11, 14, 22, 39]
      7_execution: "sana-core вызывает детерминированную процедуру PL/pgSQL (fn_create_transaction)"[cite: 2, 6, 8, 9, 11, 14, 17, 18, 28, 30]
    egestion_loop:
      1_snapshot_result: "БД обновляет user_snapshots и возвращает результат в sana-core"[cite: 2, 17, 18, 28, 35, 53]
      2_voice_orchestration: "Исходящий Дирижёр подбирает голоса ответа (Sana Zen / Consigliere / Nostradamus)"[cite: 17, 18, 28, 35]
      3_synthesis: "Output Agent генерирует эмпатичный текст на основе сухих фактов SQL"[cite: 8, 17, 18, 26, 28, 35]
      4_delivery: "Отправка сообщения через Push/WebSocket в клиентский интерфейс"[cite: 2, 28, 33, 35, 36]
      5_zero_persistence_cleanup: "Мгновенное физическое уничтожение сырых медиа-файлов из S3 и RAM"[cite: 2, 6, 12, 17, 18, 22, 24, 33, 35]

data_governance:
  database:
    engine: "PostgreSQL 16+"[cite: 34]
    principle: "Logic in Database (вся финансовая математика внутри PL/pgSQL)"[cite: 2, 8, 11, 14, 18, 23, 48]
    immutability: "DELETE/UPDATE на ledger_transactions запрещены триггерами; ошибки исправляются компенсирующими транзакциями"[cite: 11, 38, 48, 54, 59]
    multi_tenancy: "Row-Level Security (RLS) фильтрация на уровне ядра СУБД"[cite: 16, 32, 39, 40, 48]
  ephemeral_cache:
    engine: "Redis Cluster"[cite: 34]
    strict_invariant: "Категорически запрещено хранить данные Ledger/транзакций; только кэш FX, сессии и блокировки"[cite: 2, 12, 16, 18, 34]
```
