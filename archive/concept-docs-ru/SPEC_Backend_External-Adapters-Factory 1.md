**type:** #type/doc **note status:** #state/active **active role:** #role/architect **architect area:** #area/projects/sana/arch/backend **tags:** #rust #abstraction #action #AI #brain #k8s #docker #hash **created:** 2026-01-31 **updated:** 2026-01-31


--------------------------------------------------------------------------------

**Статус:** Final Engineering Specification **Слой:** Infrastructure & Abstraction Layer **Стек:** Rust Traits, `async_trait`, HashiCorp Vault / K8s Secrets **Принцип:** «Provider Agnostic» — Код знает *что* делать, но не *кем* это выполняется.


--------------------------------------------------------------------------------

# 1. Философия: Архитектура Адаптеров

Бизнес-логика Sana (Ledger, Tax Engine, Nostradamus) никогда не должна зависеть от конкретных внешних API. Мы строим систему, где замена Gemini на Claude или Binance на CoinGecko — это вопрос смены конфигурации, а не переписывания кода.

## 1.1. Паттерн Фабрики (The Factory Pattern)

В коде ядра запрещено использование SDK вендоров (например, `openai-sdk` или `ethers-rs` напрямую в контроллерах). Вместо этого ядро обращается к **Фабрике Адаптеров**, которая в рантайме возвращает реализацию абстрактного типажа (Rust Trait).

**Поток вызова:**

**Core:** `let ai_service = AdapterFactory::get_ai_provider(Config::FastLoop);`

**Factory:** Читает конфиг, видит `provider: "groq"`, инжектирует API-ключ из Vault.

**Result:** Возвращает структуру `GroqAdapter`, реализующую типаж `ModelProvider`.

**Action:** Core вызывает метод `ai_service.invoke_agent(...)`, не зная, кто именно исполняет запрос.


--------------------------------------------------------------------------------

# 2. AI Model Provider: Когнитивная Фабрика

Управляет доступом к LLM. Ключевая особенность — динамическое переключение моделей и управление когнитивным потоком через Backend.

## 2.1. Типаж `ModelProvider`

```
#[async_trait]
pub trait ModelProvider: Send + Sync {
    // Backend передает только данные (Context Payload).
    // Промпт уже зашит внутри конкретной реализации агента или конфигурации.
    async fn invoke_agent(&self, agent_id: AgentType, payload: ContextPayload) -> Result<AgentResponse, AiError>;

    // Технический метод для подсчета токенов (Cost Control)
    async fn tokenize(&self, text: &str) -> Result<u32, AiError>;
}
```

## 2.2. Режимы работы (Loop Strategy)

Фабрика выбирает провайдера на основе контекста задачи,:

**Fast Loop (Groq / Gemini Flash):****Задачи:** Парсинг чеков, классификация транзакций, простые ответы в чате.**Приоритет:** Скорость (<500ms).

**Задачи:** Парсинг чеков, классификация транзакций, простые ответы в чате.

**Приоритет:** Скорость (<500ms).

**Slow Loop (Claude Opus / Gemini Pro):****Задачи:** Глубокая аналитика Nostradamus, эмпатичные ответы Sana Zen, сложные финансовые советы.**Приоритет:** Качество рассуждений и большое контекстное окно.

**Задачи:** Глубокая аналитика Nostradamus, эмпатичные ответы Sana Zen, сложные финансовые советы.

**Приоритет:** Качество рассуждений и большое контекстное окно.

## 2.3. Middleware: Cost & Privacy

**Cost Control:** Каждый вызов через адаптер логируется в таблицу `ai_usage_metrics` с подсчетом токенов и стоимости.

**PII Sanitization:** Адаптер автоматически применяет правила очистки данных (скрытие имен, телефонов) перед отправкой JSON-пейлоада провайдеру, соблюдая принцип «Air-Gap» для личной информации.


--------------------------------------------------------------------------------

# 3. Exchange Rate Provider: Валютная Истина

Обеспечивает работу системы «Minute-Precision FX». Курсы валют — это не константа, а поток данных.

## 3.1. Типаж `ExchangeRateProvider`

```
#[async_trait]
pub trait ExchangeRateProvider: Send + Sync {
    // Получение курса для пары (напр., BTC/USD)
    async fn get_rate(&self, pair: CurrencyPair) -> Result<Decimal, FxError>;
    // Пакетное получение курсов
    async fn get_batch_rates(&self, pairs: &[CurrencyPair]) -> Result<HashMap<CurrencyPair, Decimal>, FxError>;
}

```

## 3.2. Логика Агрегации (Consensus Logic)

Адаптер реализует логику «Справедливой цены» для исключения манипуляций или ошибок одного источника:

**Multi-Source Fetch:** Запрашивает курс одновременно у `BinanceAdapter`, `CoinGeckoAdapter` и `FixerAdapter` (для фиата).

**Outlier Removal:** Отбрасывает экстремумы (самый высокий и самый низкий курс).

**Averaging:** Вычисляет среднее значение оставшихся источников.

**Verification:** Если курс подтвержден минимум двумя источниками, он помечается как `is_verified = true` в `fx_rates_history`.


--------------------------------------------------------------------------------

# 4. Node Provider: Блокчейн-Шлюз

Используется спутником `sana-crypto-sync` для чтения данных из блокчейнов. Мы не доверяем одной ноде.

## 4.1. Типаж `ChainInformer`

```
#[async_trait]
pub trait ChainInformer: Send + Sync {
    async fn get_balance(&self, address: &str) -> Result<BigDecimal, ChainError>;
    async fn get_transactions(&self, address: &str, cursor: Option<String>) -> Result<Vec<Tx>, ChainError>;
    async fn get_block_height(&self) -> Result<u64, ChainError>;
}

```

## 4.2. Ротация и Failover

**Round-Robin:** Фабрика чередует запросы между Infura, Alchemy и собственными нодами для распределения нагрузки и обхода Rate Limits.

**Consistency Check:** Для критических операций (крупные депозиты) адаптер может запросить данные у двух провайдеров и сверить `block_hash`, чтобы убедиться в отсутствии форка или отставания ноды.


--------------------------------------------------------------------------------

# 5. Notification Provider: Коммуникационный Шлюз

Абстракция над каналами доставки сообщений пользователю (помимо основного ответа в чате).

## 5.1. Типаж `NotificationSender`

```
#[async_trait]
pub trait NotificationSender: Send + Sync {
    async fn send_otp(&self, target: &str, code: &str) -> Result<(), NotifyError>;
    async fn send_alert(&self, user_id: Uuid, message: &str, priority: Priority) -> Result<(), NotifyError>;
}

```

## 5.2. Реализации

**EmailAdapter:** Используется для отправки OTP-кодов при входе (через SMTP или сервисы типа SendGrid).

**TelegramPushAdapter:** Используется для критических алертов (например, от Nostradamus о кассовом разрыве), даже если пользователь не активен в данный момент в чате.

**SystemBroadcast:** Интеграция с таблицей `system_announcements` для массовых уведомлений (техработы, релизы).


--------------------------------------------------------------------------------

# 6. Инфраструктура: Безопасность и Отказоустойчивость

## 6.1. Secret Injection

API-ключи (например, `GEMINI_API_KEY`, `ETHERSCAN_TOKEN`) никогда не хранятся в коде или Docker-образе.

При старте пода (`sana-core`), Kubernetes инжектирует секреты из **HashiCorp Vault** в переменные окружения процесса.

Фабрика считывает их при инициализации структуры адаптера `new(api_key: String)`.

## 6.2. Circuit Breaker

Фабрика реализует паттерн Circuit Breaker. Если внешний сервис (например, Stripe) начинает возвращать ошибки 500, адаптер временно «размыкает цепь», прекращая отправку запросов на короткое время, и переключается на резервного провайдера (Failover), чтобы не блокировать потоки ядра.


--------------------------------------------------------------------------------

# Резюме

**External Adapters Factory** превращает Backend Sana в модульный конструктор, защищенный от внешнего хаоса. Ядро остается чистым и детерминированным, делегируя взаимодействие с нестабильным внешним миром специализированным и взаимозаменяемым адаптерам.
