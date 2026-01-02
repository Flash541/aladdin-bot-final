// --- TELEGRAM INIT ---
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Set Theme Colors
document.documentElement.style.setProperty('--tg-theme-bg', tg.themeParams.bg_color || '#0b0e11');
document.documentElement.style.setProperty('--tg-theme-text', tg.themeParams.text_color || '#ffffff');

// --- CONFIG ---
const API_BASE = "";

// --- LOCALIZATION ---
const translations = {
    en: {
        welcome: "Welcome Back",
        total_balance: "Total Portfolio Balance",
        top_up: "Top Up",
        copy_trading: "Copy Trading",
        active_strategies: "Active Strategies",
        my_exchanges: "My Exchanges",
        connect_new: "Connect New Exchange",
        profile: "Settings",
        language: "Language",
        user_id: "User ID",
        credits: "Aladdin Credits",
        home: "Home",
        exchanges: "Exchanges",
        settings: "Settings",
        // Wizard
        wiz_title: "Setup Copy Trading",
        wiz_step1: "Select Strategy",
        wiz_step2: "Select Exchange",
        wiz_step3: "Connection Details",
        strat_ratner: "Ratner (Futures)",
        strat_ratner_desc: "Binance, Bybit, etc.",
        strat_cgt: "TradeMax (Spot)",
        strat_cgt_desc: "OKX Only",
        btn_next: "Next",
        btn_connect: "Connect",
        success: "Connected Successfully!",
        reserve_title: "Set Reserve Amount",
        reserve_desc: "Amount to keep in USDT (not used for trading).",
        save: "Save",
        // TopUp
        topup_title: "Top Up Credits",
        topup_desc: "Credits are used for performance fees (40% of profit).",
        pay: "Pay"
    },
    ru: {
        welcome: "С возвращением",
        total_balance: "Общий Баланс",
        top_up: "Пополнить",
        copy_trading: "Копитрейдинг",
        active_strategies: "Активные Стратегии",
        my_exchanges: "Мои Биржи",
        connect_new: "Подключить Биржу",
        profile: "Настройки",
        language: "Язык",
        user_id: "ID Пользователя",
        credits: "Кредиты Aladdin",
        home: "Главная",
        exchanges: "Биржи",
        settings: "Настройки",
        // Wizard
        wiz_title: "Настройка Копитрейдинга",
        wiz_step1: "Выберите Стратегию",
        wiz_step2: "Выберите Биржу",
        wiz_step3: "Детали Подключения",
        strat_ratner: "Ratner (Фьючерсы)",
        strat_ratner_desc: "Binance, Bybit и др.",
        strat_cgt: "TradeMax (Спот)",
        strat_cgt_desc: "Только OKX",
        btn_next: "Далее",
        btn_connect: "Подключить",
        success: "Успешно подключено!",
        reserve_title: "Настроить Резерв",
        reserve_desc: "Сумма в USDT, которая Не торгуется.",
        save: "Сохранить",
        // TopUp
        topup_title: "Пополнить Кредиты",
        topup_desc: "Кредиты используются для оплаты комиссии (40% от прибыли).",
        pay: "Оплатить"
    },
    uk: {
        welcome: "З поверненням",
        total_balance: "Загальний Баланс",
        top_up: "Поповнити",
        copy_trading: "Копітрейдинг",
        active_strategies: "Активні Стратегії",
        my_exchanges: "Мої Біржі",
        connect_new: "Підключити Біржу",
        profile: "Налаштування",
        language: "Мова",
        user_id: "ID Користувача",
        credits: "Кредити Aladdin",
        home: "Головна",
        exchanges: "Биржі",
        settings: "Налаштування",
        // Wizard
        wiz_title: "Налаштування Копітрейдингу",
        wiz_step1: "Оберіть Стратегію",
        wiz_step2: "Оберіть Біржу",
        wiz_step3: "Деталі Підключення",
        strat_ratner: "Ratner (Ф'ючерси)",
        strat_ratner_desc: "Binance, Bybit та ін.",
        strat_cgt: "TradeMax (Спот)",
        strat_cgt_desc: "Тільки OKX",
        btn_next: "Далі",
        btn_connect: "Підключити",
        success: "Успішно підключено!",
        reserve_title: "Налаштувати Резерв",
        reserve_desc: "Сума в USDT, яка Не торгується.",
        save: "Зберегти",
        // TopUp
        topup_title: "Поповнити Кредити",
        topup_desc: "Кредити використовуються для оплати комісії (40% від прибутку).",
        pay: "Сплатити"
    }
};

let currentLang = 'en';

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", async () => {
    // 1. User Info
    const user = tg.initDataUnsafe.user;
    if (user) {
        document.getElementById("user-name").innerText = user.first_name || "Trader";
        if (user.photo_url) {
            document.getElementById("user-avatar").src = user.photo_url;
        }
        document.getElementById("user-id-disp").innerText = user.id;

        // 2. Fetch User Data (Language + Balance)
        await fetchUserData(user.id);
    } else {
        console.warn("No Telegram User detected. Using Mock.");
        document.getElementById("user-name").innerText = "Dev User";
        // mock logic for dev...
    }

    // 4. Setup Logic
    setupTabs();
    setupWizard();
    setupReserveModal();
    setupTopUpModal();
    setupLanguageSelector();
});

async function fetchUserData(userId) {
    try {
        const res = await fetch(`${API_BASE}/api/data?user_id=${userId}`);
        if (!res.ok) throw new Error("API Error");
        const data = await res.json();

        // 1. Set Language
        if (data.language && translations[data.language]) {
            setLanguage(data.language);
        }

        // 2. Render Balances
        animateValue("total-balance", 0, data.totalBalance, 1000);
        document.getElementById("credits-bal").innerText = data.credits.toFixed(2);

        // 3. Render Lists
        renderExchanges(data.exchanges);
        renderActiveStrategies(data.exchanges);

    } catch (e) {
        console.error("Fetch failed", e);
    }
}

function setLanguage(lang) {
    currentLang = lang;
    const t = translations[lang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.innerText = t[key];
    });
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.lang-btn[data-lang="${lang}"]`)?.classList.add('active');
}

async function saveLanguage(lang) {
    const user = tg.initDataUnsafe.user;
    if (!user) return;
    try {
        await fetch(`${API_BASE}/api/language`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id, language: lang })
        });
        setLanguage(lang);
    } catch (e) { console.error(e); }
}

// --- RENDER FUNCTIONS ---
function renderExchanges(exchanges) {
    const list = document.getElementById("exchange-list");
    list.innerHTML = "";

    if (!exchanges || exchanges.length === 0) {
        list.innerHTML = `<div style="padding:20px; text-align:center; color:#888;">No exchanges connected</div>`;
        return;
    }

    exchanges.forEach(ex => {
        const isConnected = ex.status === "Connected";
        const statusClass = isConnected ? "status-green" : "status-red";

        const html = `
            <div class="list-item">
                <div class="item-icon">${ex.icon || '🔹'}</div>
                <div class="item-content">
                    <div class="item-title">${ex.name}</div>
                    <div class="item-subtitle">
                        <span class="status-dot ${statusClass}"></span>${ex.status} • ${ex.strategy === 'cgt' ? 'Spot' : 'Fut'}
                    </div>
                </div>
                <div class="item-value">
                    <div class="item-amount">$${ex.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
                    <div class="reserve-badge" onclick="openReserveModal('${ex.name}', ${ex.reserve})">
                        🔒 $${ex.reserve}
                    </div>
                </div>
            </div>
        `;
        list.insertAdjacentHTML('beforeend', html);
    });
}

function renderActiveStrategies(exchanges) {
    const container = document.getElementById("active-strategies-list");
    if (!container) return;
    container.innerHTML = "";

    const active = exchanges ? exchanges.filter(ex => ex.status === "Connected") : [];

    if (active.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:10px; color:#666;">No active strategies</div>';
        return;
    }

    active.forEach(ex => {
        const stratName = ex.strategy === 'cgt' ? 'TradeMax' : 'Ratner';
        const type = ex.strategy === 'cgt' ? 'Spot' : 'Futures';

        const html = `
            <div class="list-item">
                <div class="item-icon">🧞‍♂️</div>
                <div class="item-content">
                    <div class="item-title">${stratName}</div>
                    <div class="item-subtitle">${ex.name} • ${type}</div>
                </div>
                <div class="item-value">
                    <div class="item-amount text-gold">Active</div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}

// --- WIZARD LOGIC ---
let wizardData = { strategy: 'ratner', exchange: 'binance', reserve: 0, apiKey: '', secret: '', password: '' };
let currentStep = 1;

function setupWizard() {
    // Buttons
    const btnOpen = document.getElementById("btn-copy-trading");
    const modal = document.getElementById("modal-wizard");
    const btnClose = document.getElementById("btn-close-wizard");

    if (btnOpen) btnOpen.onclick = () => { resetWizard(); modal.style.display = "flex"; };
    if (btnClose) btnClose.onclick = () => modal.style.display = "none";

    // Step 1: Strategy
    document.querySelectorAll('.strategy-card').forEach(card => {
        card.onclick = () => {
            document.querySelectorAll('.strategy-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            wizardData.strategy = card.dataset.strategy;

            filterExchanges(wizardData.strategy);
            goToStep(2);
        };
    });

    // Step 2: Exchange
    document.querySelectorAll('.exchange-option').forEach(opt => {
        opt.onclick = () => {
            document.querySelectorAll('.exchange-option').forEach(c => c.classList.remove('selected'));
            opt.classList.add('selected');
            wizardData.exchange = opt.dataset.exchange;

            setupApiFields(wizardData.exchange);
            goToStep(3);
        };
    });

    // Step 3: API Keys
    document.getElementById("btn-submit-api").onclick = async () => {
        wizardData.apiKey = document.getElementById("inp-key").value;
        wizardData.secret = document.getElementById("inp-secret").value;
        wizardData.password = document.getElementById("inp-pass").value;
        wizardData.reserve = parseFloat(document.getElementById("inp-reserve-init").value) || 0;

        await submitConnection();
    };
}

function filterExchanges(strategy) {
    const opts = document.querySelectorAll('.exchange-option');
    opts.forEach(opt => {
        const ex = opt.dataset.exchange;
        if (strategy === 'cgt') {
            // OKX Only
            opt.style.display = ex === 'okx' ? 'block' : 'none';
        } else {
            // Ratner: Not OKX
            opt.style.display = ex !== 'okx' ? 'block' : 'none';
        }
    });
}

function setupApiFields(exchange) {
    const passGroup = document.getElementById("group-pass");
    if (exchange === 'okx') passGroup.style.display = 'block';
    else passGroup.style.display = 'none';
}

function resetWizard() {
    currentStep = 1;
    showStep(1);
    document.getElementById("form-wizard-api").reset();
    document.querySelectorAll('.selected').forEach(e => e.classList.remove('selected'));
}

function goToStep(step) {
    currentStep = step;
    showStep(step);
}

function showStep(step) {
    document.querySelectorAll('.wizard-step').forEach(el => el.style.display = 'none');
    document.getElementById(`step-${step}`).style.display = 'block';
}

async function submitConnection() {
    const user = tg.initDataUnsafe.user;
    if (!user) return;

    tg.MainButton.showProgress();
    try {
        const res = await fetch(`${API_BASE}/api/connect`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: user.id,
                exchange: wizardData.exchange,
                api_key: wizardData.apiKey,
                secret: wizardData.secret,
                password: wizardData.password,
                strategy: wizardData.strategy,
                reserve: wizardData.reserve
            })
        });

        tg.MainButton.hideProgress();
        if (res.ok) {
            goToStep(4);
            setTimeout(() => {
                document.getElementById("modal-wizard").style.display = "none";
                fetchUserData(user.id);
            }, 2000);
        } else {
            const dat = await res.json();
            tg.showAlert("Connection Failed: " + dat.detail);
        }
    } catch (e) {
        tg.MainButton.hideProgress();
        tg.showAlert("Error: " + e.message);
    }
}

// --- RESERVE MODAL ---
let editingExchange = null;
function setupReserveModal() {
    const modal = document.getElementById("modal-reserve");
    const btnClose = document.getElementById("btn-close-reserve");
    const btnSave = document.getElementById("btn-save-reserve");
    if (btnClose) btnClose.onclick = () => modal.style.display = "none";
    if (btnSave) btnSave.onclick = async () => {
        const amt = parseFloat(document.getElementById("inp-reserve-edit").value) || 0;
        await updateReserve(editingExchange, amt);
        modal.style.display = "none";
    };
    window.openReserveModal = (exchange, currentVal) => {
        editingExchange = exchange;
        document.getElementById("reserve-exchange-title").innerText = exchange.toUpperCase();
        document.getElementById("inp-reserve-edit").value = currentVal;
        modal.style.display = "flex";
    };
}
async function updateReserve(exchange, amount) {
    const user = tg.initDataUnsafe.user;
    if (!user) return;
    tg.MainButton.showProgress();
    try {
        await fetch(`${API_BASE}/api/reserve`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id, exchange: exchange, reserve: amount })
        });
        tg.MainButton.hideProgress();
        fetchUserData(user.id);
    } catch (e) { tg.MainButton.hideProgress(); console.error(e); }
}

// --- TOP UP MODAL ---
function setupTopUpModal() {
    const btnOpen = document.querySelectorAll('[data-action="topup"]');
    const modal = document.getElementById("modal-topup");
    const btnClose = document.getElementById("btn-close-topup");
    const btnPay = document.getElementById("btn-pay");

    btnOpen.forEach(b => b.onclick = () => modal.style.display = "flex");
    if (btnClose) btnClose.onclick = () => modal.style.display = "none";

    if (btnPay) btnPay.onclick = async () => {
        const txId = document.getElementById("inp-topup-txid").value.trim();
        if (!txId || txId.length < 10) return tg.showAlert("Invalid TxID");

        await submitTopUp(txId);
        modal.style.display = "none";
    };

    window.copyAddress = () => {
        const addr = "0x6c639cac616254232d9c4d51b1c3646132b46c4a";
        navigator.clipboard.writeText(addr);
        tg.showAlert("Address Copied!");
    };
}
async function submitTopUp(txId) {
    const user = tg.initDataUnsafe.user;
    if (!user) return;
    tg.MainButton.showProgress();
    try {
        const res = await fetch(`${API_BASE}/api/topup`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id, tx_id: txId })
        });
        const d = await res.json();
        tg.MainButton.hideProgress();

        if (!res.ok) throw new Error(d.detail || "Failed");

        tg.showAlert(d.msg || "Top Up Successful!");
        fetchUserData(user.id);
    } catch (e) {
        tg.MainButton.hideProgress();
        tg.showAlert("Verification Failed: " + e.message);
    }
}

// --- NAVIGATION ---
function setupTabs() {
    const pads = document.querySelectorAll('.nav-item');
    const pages = document.querySelectorAll('.page');
    pads.forEach(pad => {
        pad.addEventListener('click', () => {
            // Handle settings via param if any
            const target = pad.dataset.target;
            pads.forEach(p => p.classList.remove('active'));
            pages.forEach(p => p.classList.remove('active'));
            pad.classList.add('active');
            document.getElementById(target).classList.add('active');
            if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        });
    });
}
function setupLanguageSelector() {
    document.querySelectorAll('.lang-btn').forEach(btn => btn.onclick = () => saveLanguage(btn.dataset.lang));
}
function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    const step = (timestamp) => {
        if (!obj.startTimestamp) obj.startTimestamp = timestamp;
        const progress = Math.min((timestamp - obj.startTimestamp) / duration, 1);
        obj.innerHTML = "$" + (progress * end).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (progress < 1) window.requestAnimationFrame(step);
        else obj.innerHTML = "$" + end.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    window.requestAnimationFrame(step);
}
