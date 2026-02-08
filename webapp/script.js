// --- INITIAL VARIABLES ---
const API_BASE = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost') ? 'http://127.0.0.1:8001' : '';
let tg = null;

// --- SPLASH LOGIC (Defined early to ensure availability) ---
window.dismissSplash = function () {
    const splash = document.getElementById('splash-screen');
    if (!splash) return;

    // Smooth fade out
    splash.style.opacity = '0';
    setTimeout(() => {
        splash.style.display = 'none';
        // Auto-show main content animation if needed
    }, 500);

    // Haptic if available
    if (window.tg && tg.HapticFeedback) {
        try { tg.HapticFeedback.impactOccurred('light'); } catch (e) { }
    }
};

// --- TELEGRAM INIT ---
try {
    if (window.Telegram && window.Telegram.WebApp) {
        tg = window.Telegram.WebApp;
        tg.expand();
        try { tg.enableClosingConfirmation(); } catch (e) { }

        document.documentElement.style.setProperty('--tg-theme-bg', tg.themeParams.bg_color || '#0B0B0B');
        document.documentElement.style.setProperty('--tg-theme-text', tg.themeParams.text_color || '#ffffff');
    } else {
        // Mock for browser testing
        console.warn("Telegram WebApp not detected. Using mock.");
        tg = {
            initDataUnsafe: { user: { id: 12345, first_name: "Test User" } },
            ready: () => { },
            expand: () => { },
            MainButton: { showProgress: () => { }, hideProgress: () => { } },
            HapticFeedback: { impactOccurred: () => { } },
            themeParams: {}
        };
    }
} catch (e) {
    console.error("TG Init Error:", e);
}

// === ACTION BUTTONS ===
function setupActionButtons() {
    // Top Up Button
    const topUpBtn = document.querySelector('[data-action="topup"]');
    if (topUpBtn) {
        topUpBtn.onclick = async () => {
            const modal = document.getElementById('modal-topup');
            modal.style.display = 'flex';
            await fetchDepositAddress();
            if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        };
    }

    // Copy Trading Button
    const copyTradeBtn = document.getElementById('btn-copy-trading');
    if (copyTradeBtn) {
        copyTradeBtn.onclick = () => {
            try {
                console.log('[DEBUG] Copy Trade Btn Clicked');
                const modal = document.getElementById('modal-copytrading');
                if (!modal) {
                    throw new Error("Modal 'modal-copytrading' not found in DOM");
                }

                modal.style.display = 'flex';

                if (typeof showCTStep === 'function') {
                    showCTStep('strategy');
                } else {
                    throw new Error("Function 'showCTStep' is not defined");
                }

                if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            } catch (e) {
                console.error('[ERROR] Copy Trading Login Failed:', e);
                alert("DEBUG ERROR: " + e.message);
            }
        };
    }
}

// === MODALS ===
// --- LOCALIZATION ---
const translations = {
    en: {
        welcome: "Welcome Back",
        lbl_total_balance: "Portfolio Value",
        btn_topup: "Top Up Fees",
        btn_copy_trade: "Copy Trading",
        active_strategies: "Active Strategies",
        view_all: "View All",
        my_exchanges: "My Exchanges",
        settings: "Settings",
        language: "Language",
        user_id: "User ID",
        lbl_alladeen_fees: "Balance USDT",
        wiz_title: "Setup Copytrading",
        btn_connect: "Connect",
        success: "Success!",
        reserve_title: "Trading Capital",
        save: "Save",
        top_up_title: "Top Up Balance",
        top_up_purpose_header: "Purpose of Top Up",
        top_up_purpose_desc: "This balance is used to pay for service fees and copy-trading commissions.<br><br>Sending USDT to the address below will automatically credit your account.",
        address_label: "Address",
        instruction_bottom: "Send USDT (BEP-20) to this address.<br>The balance will be credited automatically.",
        btn_withdraw: "Withdraw Funds",
        withdraw_title: "Withdraw USDT",
        available_balance: "Available Balance",
        withdraw_amount_label: "Amount (USDT)",
        withdraw_wallet_label: "Wallet Address (BEP-20)",
        withdraw_submit: "Submit Request",
        withdraw_success: "Withdrawal request submitted!",
        err_invalid_amount: "Invalid amount",
        err_insufficient_balance: "Insufficient balance",
        err_invalid_wallet: "Invalid wallet address (must start with 0x and be 42 characters)",
        lbl_trading_capital: "Trading Capital",
        msg_edit_reserve_prompt: "Amount reserved for this strategy.",
        lbl_risk_per_trade: "Risk per Trade",
        msg_edit_risk_prompt: "Percentage of capital risking per trade.",
        btn_disconnect: "Disconnect Strategy",
        btn_apply_changes: "Apply Changes",

        // Analyzer Modal
        analyzer_title: "AI Chart Analyzer",
        analyzer_description: "<strong style='color: #0660F9;'>Black Aladdin</strong> — is an AI analyst that studies your charts and provides trading signals.<br><br><strong>How it works:</strong><br>• Upload a chart screenshot<br>• AI identifies ticker and timeframe<br>• Get entry points, targets and stop-loss<br>• See confidence level and detailed notes",
        upload_chart: "Tap to upload chart",
        analyzing_market: "Analyzing market structure...",
        timeframe: "Timeframe",
        confidence: "Confidence",
        entry: "Entry:",
        target: "Target:",
        stop: "Stop:",
        explain_logic: "Explain Logic",

        // Referral Modal
        referral_program: "Referral Program",
        referral_earn_text: "Earn commission from your referrals' profitable trades:",
        level_1: "Level 1",
        level_2: "Level 2",
        level_3: "Level 3",
        commission_20: "20% commission",
        commission_7: "7% commission",
        commission_3: "3% commission",
        referrals: "referrals",
        get_referral_link: "Get Your Referral Link",
        btn_analyze: "Analyze",
        min_balance_warning: "Minimum trading balance: 100 USDT",

        // Coin Configuration
        configure_coins: "Configure Coins",
        trading_capital_usdt: "Trading Capital (USDT)",
        risk_per_trade_pct: "Risk per Trade (%)",
        minimum_5_usdt: "Minimum 5 USDT",
        connect_okx: "Connect OKX",

        // Coin Management
        manage_coins_title: "Manage Coins",
        btn_add_new_coin: "+ Add New Coin",
        select_coin_to_add: "Select Coin to Add",
        edit_coin: "Edit Coin",
        remove_coin: "Remove Coin",
        confirm_remove_coin: "Are you sure you want to remove this coin?",
        capital: "Capital",
        risk: "Risk",

        // Validation
        err_capital_too_low: "Capital must be at least 100 USDT",
        err_invalid_risk: "Risk must be between 0.1% and 10%",

        // Toasts
        toast_changes_applied: "Changes Applied",
        toast_strategy_disconnected: "Strategy Disconnected",
        toast_okx_connected: "OKX Connected",
        toast_coin_updated: "Coin updated",
        toast_coin_removed: "Coin removed",
        toast_coin_added: "Coin added",
        toast_exchange_disconnected: "Exchange disconnected",
        toast_address_copied: "Address Copied",

        // Coin Management (modals)
        edit_coin_title: "Edit Coin",
        add_coin_title: "Add Coin",
        trading_capital_label: "Trading Capital (USDT)",
        risk_per_trade_label: "Risk per Trade (%)",
        btn_save_changes: "Save Changes",
        btn_remove_coin: "Remove Coin",
        no_coins_yet: "No coins configured yet",
        no_coins_hint: "Click below to add a coin",
        all_coins_added: "All coins already added",
        manage_allocations: "Manage Allocations"
    },
    ru: {
        welcome: "С возвращением",
        lbl_total_balance: "Стоимость портфеля",
        btn_topup: "Пополнить",
        btn_copy_trade: "Копитрейдинг",
        active_strategies: "Активные стратегии",
        view_all: "Все",
        my_exchanges: "Мои биржи",
        settings: "Настройки",
        language: "Язык",
        user_id: "ID пользователя",
        lbl_alladeen_fees: "Баланс USDT",
        wiz_title: "Настройка копитрейдинга",
        btn_connect: "Подключить",
        success: "Успешно!",
        reserve_title: "Торговый капитал",
        save: "Сохранить",
        top_up_title: "Пополнить",
        top_up_purpose_header: "Для чего это нужно?",
        top_up_purpose_desc: "Этот баланс используется для оплаты сервисных сборов и комиссий копитрейдинга.<br><br>Отправьте USDT на адрес ниже для автоматического пополнения счета.",
        address_label: "Адрес",
        instruction_bottom: "Отправьте USDT (BEP-20) на этот адрес.<br>Баланс будет зачислен автоматически.",
        btn_withdraw: "Вывод средств",
        withdraw_title: "Вывод USDT",
        available_balance: "Доступно",
        withdraw_amount_label: "Сумма (USDT)",
        withdraw_wallet_label: "Адрес кошелька (BEP-20)",
        withdraw_submit: "Отправить запрос",
        withdraw_success: "Запрос на вывод отправлен!",
        err_invalid_amount: "Неверная сумма",
        err_insufficient_balance: "Недостаточно средств",
        err_invalid_wallet: "Неверный адрес (должен начинаться с 0x и быть длиной 42 символа)",
        lbl_trading_capital: "Торговый капитал",
        msg_edit_reserve_prompt: "Сумма, зарезервированная для этой стратегии.",
        lbl_risk_per_trade: "Риск на сделку",
        msg_edit_risk_prompt: "Процент капитала, рискуemый на каждую сделку.",
        btn_disconnect: "Отключить стратегию",
        btn_apply_changes: "Применить изменения",

        // Analyzer Modal
        analyzer_title: "AI Анализ графиков",
        analyzer_description: "<strong style='color: #0660F9;'>Black Aladdin</strong> — это AI-аналитик, который изучает ваши графики и предоставляет торговые сигналы.<br><br><strong>Как работает:</strong><br>• Загрузите скриншот графика<br>• AI определит тикер и таймфрейм<br>• Получите точки входа, цели и стоп-лосс<br>• См. уровень уверенности и детальные заметки",
        upload_chart: "Нажмите для загрузки графика",
        analyzing_market: "Анализируем рыночную структуру...",
        timeframe: "Таймфрейм",
        confidence: "Уверенность",
        entry: "Вход:",
        target: "Цель:",
        stop: "Стоп:",
        explain_logic: "Объяснить логику",
        btn_analyze: "Анализ",
        // Referral Modal
        referral_program: "Реферальная программа",
        referral_earn_text: "Зарабатывайте комиссию с прибыльных сделок ваших рефералов:",
        level_1: "Уровень 1",
        level_2: "Уровень 2",
        level_3: "Уровень 3",
        commission_20: "20% комиссия",
        commission_7: "7% комиссия",
        commission_3: "3% комиссия",
        referrals: "рефералов",
        get_referral_link: "Получить реферальную ссылку",
        min_balance_warning: "Минимальный торговый баланс: 100 USDT",

        // Coin Configuration
        configure_coins: "Настройка монет",
        trading_capital_usdt: "Торговый капитал (USDT)",
        risk_per_trade_pct: "Риск на сделку (%)",
        minimum_5_usdt: "Минимум 5 USDT",
        connect_okx: "Подключить OKX",

        // Coin Management  
        manage_coins_title: "Управление монетами",
        btn_add_new_coin: "+ Добавить монету",
        select_coin_to_add: "Выберите монету",
        edit_coin: "Редактировать",
        remove_coin: "Удалить",
        confirm_remove_coin: "Вы уверены, что хотите удалить эту монету?",
        capital: "Капитал",
        risk: "Риск",

        // Validation
        err_capital_too_low: "Капитал должен быть минимум 5 USDT",
        err_invalid_risk: "Риск должен быть от 0.1% до 10%",

        // Toasts
        toast_changes_applied: "Изменения сохранены",
        toast_strategy_disconnected: "Стратегия отключена",
        toast_okx_connected: "OKX подключён",
        toast_coin_updated: "Монета обновлена",
        toast_coin_removed: "Монета удалена",
        toast_coin_added: "Монета добавлена",
        toast_exchange_disconnected: "Биржа отключена",
        toast_address_copied: "Адрес скопирован",

        // Coin Management (modals)
        edit_coin_title: "Редактировать монету",
        add_coin_title: "Добавить монету",
        trading_capital_label: "Торговый капитал (USDT)",
        risk_per_trade_label: "Риск на сделку (%)",
        btn_save_changes: "Сохранить",
        btn_remove_coin: "Удалить монету",
        no_coins_yet: "Монеты ещё не настроены",
        no_coins_hint: "Нажмите ниже чтобы добавить",
        all_coins_added: "Все монеты уже добавлены",
        manage_allocations: "Управление аллокациями"
    },
    uk: {
        welcome: "З поверненням",
        lbl_total_balance: "Портфель",
        btn_topup: "Поповнити",
        btn_copy_trade: "Копі-Трейд",
        active_strategies: "Активні Стратегії",
        view_all: "Всі",
        my_exchanges: "Мої Біржі",
        btn_analyze: "Аналіз",
        settings: "Налаштування",
        language: "Мова",
        user_id: "ID користувача",
        lbl_alladeen_fees: "Баланс USDT",
        wiz_title: "Налаштування копітрейдингу",
        btn_connect: "Підключити",
        success: "Успіх!",
        reserve_title: "Торговий Капітал",
        save: "Зберегти",
        top_up_title: "Поповнити",
        top_up_purpose_header: "Для чого це потрібно?",
        top_up_purpose_desc: "Цей баланс використовується для оплати сервісних зборів та комісій копітрейдингу.<br><br>Надішліть USDT на адресу нижче для автоматичного поповнення рахунку.",
        address_label: "Адреса",
        instruction_bottom: "Надішліть USDT (BEP-20) на цю адресу.<br>Баланс буде зараховано автоматично.",
        btn_withdraw: "Вивести кошти",
        withdraw_title: "Вивід USDT",
        available_balance: "Доступно",
        withdraw_amount_label: "Сума (USDT)",
        withdraw_wallet_label: "Адреса гаманця (BEP-20)",
        withdraw_submit: "Відправити запит",
        withdraw_success: "Запит на вивід відправлено!",
        err_invalid_amount: "Невірна сума",
        err_insufficient_balance: "Недостатньо коштів",
        err_invalid_wallet: "Невірна адреса (повинна починатися з 0x та бути довжиною 42 символи)",
        lbl_trading_capital: "Торговий капітал",
        msg_edit_reserve_prompt: "Сума, зарезервована для цієї стратегії.",
        lbl_risk_per_trade: "Ризик на угоду",
        msg_edit_risk_prompt: "Відсоток капіталу, що ризикується на кожну угоду.",
        btn_disconnect: "Від'єднати стратегію",
        btn_apply_changes: "Застосувати зміни",

        // Analyzer Modal
        analyzer_title: "AI Аналіз графіків",
        analyzer_description: "<strong style='color: #0660F9;'>Black Aladdin</strong> — це AI-аналітик, який вивчає ваші графіки та надає торгові сигнали.<br><br><strong>Як це працює:</strong><br>• Завантажте скріншот графіка<br>• AI визначить тикер та таймфрейм<br>• Отримайте точки входу, цілі та стоп-лосс<br>• Див. рівень впевненості та детальні нотатки",
        upload_chart: "Натисніть для завантаження графіка",
        analyzing_market: "Аналізуємо ринкову структуру...",
        timeframe: "Таймфрейм",
        confidence: "Впевненість",
        entry: "Вхід:",
        target: "Ціль:",
        stop: "Стоп:",
        explain_logic: "Пояснити логіку",

        // Referral Modal
        referral_program: "Реферальна програма",
        referral_earn_text: "Заробляйте комісію з прибуткових угод ваших рефералів:",
        level_1: "Рівень 1",
        level_2: "Рівень 2",
        level_3: "Рівень 3",
        commission_20: "20% комісія",
        commission_7: "7% комісія",
        commission_3: "3% комісія",
        referrals: "рефералів",
        get_referral_link: "Отримати реферальне посилання",
        min_balance_warning: "Мінімальний баланс: 100 USDT",

        // Coin Configuration
        configure_coins: "Налаштування монет",
        trading_capital_usdt: "Торговий капітал (USDT)",
        risk_per_trade_pct: "Ризик на угоду (%)",
        minimum_5_usdt: "Мінімум 5 USDT",
        connect_okx: "Підключити OKX",

        // Coin Management
        manage_coins_title: "Управління монетами",
        btn_add_new_coin: "+ Додати монету",
        select_coin_to_add: "Оберіть монету",
        edit_coin: "Редагувати",
        remove_coin: "Видалити",
        confirm_remove_coin: "Ви впевнені, що хочете видалити цю монету?",
        capital: "Капітал",
        risk: "Ризик",

        // Validation
        err_capital_too_low: "Капітал повинен бути мінімум 5 USDT",
        err_invalid_risk: "Ризик повинен бути від 0.1% до 10%",

        // Toasts
        toast_changes_applied: "Зміни збережено",
        toast_strategy_disconnected: "Стратегію від'єднано",
        toast_okx_connected: "OKX під'єднано",
        toast_coin_updated: "Монету оновлено",
        toast_coin_removed: "Монету видалено",
        toast_coin_added: "Монету додано",
        toast_exchange_disconnected: "Біржу від'єднано",
        toast_address_copied: "Адресу скопійовано",

        // Coin Management (modals)
        edit_coin_title: "Редагувати монету",
        add_coin_title: "Додати монету",
        trading_capital_label: "Торговий капітал (USDT)",
        risk_per_trade_label: "Ризик на угоду (%)",
        btn_save_changes: "Зберегти",
        btn_remove_coin: "Видалити монету",
        no_coins_yet: "Монети ще не налаштовані",
        no_coins_hint: "Натисніть нижче щоб додати",
        all_coins_added: "Всі монети вже додано",
        manage_allocations: "Управління алокаціями"
    }
};

let currentLang = 'en';

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", async () => {
    // DEBUG ALERT
    // alert("Aladdin App Loaded v45"); 

    const user = tg.initDataUnsafe.user;

    if (user) {
        const name = user.first_name || "Trader";
        // Home Header
        const elName = document.getElementById("user-name");
        if (elName) elName.innerText = name;
        if (user.photo_url) {
            const elAv = document.getElementById("user-avatar");
            if (elAv) elAv.src = user.photo_url;
        }

        // Settings Header
        const elNameSet = document.getElementById("user-name-settings");
        if (elNameSet) elNameSet.innerText = name;
        if (user.photo_url) {
            const elAvSet = document.getElementById("user-avatar-settings");
            if (elAvSet) elAvSet.src = user.photo_url;
        }

        // Exchanges Header
        const elNameEx = document.getElementById("user-name-exchanges");
        if (elNameEx) elNameEx.innerText = name;
        if (user.photo_url) {
            const elAvEx = document.getElementById("user-avatar-exchanges");
            if (elAvEx) elAvEx.src = user.photo_url;
        }

        // User ID (Settings)
        const elIdSet = document.getElementById("user-id-disp-settings");
        if (elIdSet) elIdSet.innerText = user.id;

        await fetchUserData(user.id);
    } else {
        // Fallback for non-TG environment (e.g. Browser)
        console.error("[ERROR] TG User not found. Please open this app from Telegram bot.");
        tg.showAlert("Please open this app from Telegram bot.");
        return; // Stop execution if no user

        if (document.getElementById("user-name")) document.getElementById("user-name").innerText = "Kamron";
        if (document.getElementById("user-name-settings")) document.getElementById("user-name-settings").innerText = "Kamron";
        if (document.getElementById("user-name-exchanges")) document.getElementById("user-name-exchanges").innerText = "Kamron";
        if (document.getElementById("user-id-disp-settings")) document.getElementById("user-id-disp-settings").innerText = fallbackId;

        await fetchUserData(fallbackId);
    }

    setupTabs();
    // setupWizard(); // Removed obsolete wizard
    setupReserveModal();
    setupCopyTradingModal();
    setupActionButtons();
    setupLanguageSelector();
    setupWithdrawButton();
});

async function fetchUserData(userId) {
    try {
        const res = await fetch(`${API_BASE}/api/data?user_id=${userId}`);
        const data = await res.json();
        if (data.language && translations[data.language]) setLanguage(data.language);

        // Portfolio Value = Total Balance from exchanges
        animateValue("total-balance", 0, data.totalBalance, 1000);

        // Settings page shows fee balance (credits)
        const elCredSet = document.getElementById("credits-bal-settings");
        if (elCredSet) elCredSet.innerText = data.credits.toFixed(2);

        // Settings page shows UNC balance
        const elUncSet = document.getElementById("unc-bal-settings");
        if (elUncSet) elUncSet.innerText = (data.unc_balance || 0).toFixed(2);

        renderExchanges(data.exchanges, data.credits);
        renderActiveStrategies(data.exchanges, data.credits);
    } catch (e) { console.error(e); }
}

function setLanguage(lang) {
    currentLang = lang;
    const t = translations[lang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t && t[key]) el.innerHTML = t[key]; // innerHTML allows <br>
    });

    // Update Active Button State
    document.querySelectorAll('.lang-btn').forEach(b => {
        b.classList.remove('active');
        if (b.dataset.lang === lang) b.classList.add('active');
    });
}

// --- RENDER FUNCTIONS ---
function renderExchanges(exchanges, credits = 0) {
    const list = document.getElementById("exchange-list");
    if (!list) return;
    list.innerHTML = "";

    // Filter: Show ONLY connected + Error (to debug)
    const active = exchanges ? exchanges.filter(ex => ex.status === "Connected" || ex.status === "Error") : [];

    if (active.length === 0) {
        list.innerHTML = `<div class="fade-in" style="padding:20px; text-align:center; color:#555;">No connected exchanges</div>`;
        return;
    }

    const t = translations[currentLang] || translations['en'];

    active.forEach((ex, idx) => {
        const isConnected = ex.status === "Connected";
        let stratName = 'BingBot';
        const exNameLow = ex.name.toLowerCase();
        if (exNameLow === 'okx' || ex.strategy === 'trademax' || ex.strategy === 'cgt') {
            stratName = 'TradeMax';
        } else if (exNameLow === 'bingx') {
            stratName = 'BingBot';
        }

        // Logic for "Waiting TopUp" vs "Active"
        let statusText = t.status_active || "Active";

        // Use logic from renderActiveStrategies to determine status text
        if (ex.status === "Error") {
            statusText = t.status_error || "Check API";
        } else if (credits <= 0) {
            statusText = (t.status_waiting_topup || "Waiting TopUp");
        }

        const logoPath = `logo_bots/${ex.name.toLowerCase()}.png?v=2`;
        const balance = ex.balance || 0;

        // Check if this is OKX with coin configs
        const hasCoins = ex.coins && ex.coins.length > 0;

        if (hasCoins) {
            // Hierarchical structure for OKX
            const coinDetails = {
                'BTC/USDT': { img: 'bitcoin.png' },
                'ETH/USDT': { img: 'ethereum.png' },
                'BNB/USDT': { img: 'bnb.png' },
                'OKB/USDT': { img: 'okb.png' }
            };

            let html = `
                <div class="exchange-hierarchy fade-in" style="animation-delay: ${idx * 0.1}s;">
                    <!-- Exchange Header -->
                    <div class="exchange-header">
                        <div class="exchange-header-left">
                            <img src="${logoPath}" class="exchange-icon">
                            <div>
                                <div class="exchange-name">${stratName}</div>
                                <div style="font-size: 12px; color: #9CA3AF;">${ex.coins.length} coins configured</div>
                            </div>
                        </div>
                        <div class="exchange-status ${ex.status === 'Connected' ? 'active' : 'error'}">
                            ${statusText}
                        </div>
                    </div>
                    
                    <!-- Coin List -->
                    <div class="coin-list">
            `;

            ex.coins.forEach(coin => {
                const details = coinDetails[coin.symbol] || { img: 'bitcoin.png' };
                html += `
                    <div class="coin-item" onclick="editCoinConfig('${ex.name}', '${coin.symbol}', ${coin.reserved_amount}, ${coin.risk_pct})">
                        <div class="coin-item-left">
                            <img src="coin_img/${details.img}" class="coin-item-icon">
                            <div class="coin-item-info">
                                <div class="coin-item-symbol">${coin.symbol}</div>
                                <div class="coin-item-details">$${coin.reserved_amount.toFixed(2)} / ${coin.risk_pct}%</div>
                            </div>
                        </div>
                        <div class="exchange-status active" style="font-size: 11px;">Active</div>
                    </div>
                `;
            });

            html += `
                    </div>
                    
                    <!-- Add Coin Button -->
                    <button class="btn-add-coin" onclick="openCoinManagement(tg.initDataUnsafe.user.id, '${ex.name}'); event.stopPropagation();">
                        + Add Coin
                    </button>
                </div>
            `;

            list.insertAdjacentHTML('beforeend', html);

        } else {
            // Original single-line display for non-OKX exchanges OR OKX without coins (fallback)
            const isConnectedStr = isConnected ? 'true' : 'false';

            // Determine Click Action: OKX -> Coin Management, Others -> Strategy Settings
            const clickHandler = (ex.name.toLowerCase() === 'okx')
                ? `openCoinManagement(${ex.name === 'okx' ? 'tg.initDataUnsafe.user.id' : '0'}, '${ex.name}')`
                : `openStrategySettings('${ex.name}', ${ex.reserve || 0}, ${ex.risk || 1}, ${isConnectedStr}, ${balance}, '${statusText}')`;

            // Wrap ID properly if needed or pass user.id from closure if available. 
            // Actually, openCoinManagement needs userId. In renderExchanges, we don't have user object directly accessible in scope easily? 
            // Wait, we can use `tg.initDataUnsafe.user.id` or fetch it.
            // Let's use `tg.initDataUnsafe.user.id` which is global-ish in this context.

            // Simplified logic for replacement:
            if (ex.name.toLowerCase() === 'okx') {
                list.insertAdjacentHTML('beforeend', `
                    <div class="strategy-item fade-in" onclick="openCoinManagement(tg.initDataUnsafe.user.id, '${ex.name}')" style="animation-delay: ${idx * 0.1}s; justify-content: space-between; cursor: pointer;">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <div class="strat-icon"><img src="${logoPath}"></div>
                            <div class="strat-info">
                                <div class="strat-title">${stratName}</div>
                                <div class="strat-desc" style="color: #aaa;">${statusText}</div>
                            </div>
                        </div>
                        <div style="text-align:right;">
                             <div class="strat-title" style="font-size:16px;">$${balance.toFixed(2)}</div>
                        </div>
                    </div>
                 `);
            } else {
                list.insertAdjacentHTML('beforeend', `
                    <div class="strategy-item fade-in" onclick="openStrategySettings('${ex.name}', ${ex.reserve || 0}, ${ex.risk || 1}, ${isConnectedStr}, ${balance}, '${statusText}');" style="animation-delay: ${idx * 0.1}s; justify-content: space-between; cursor: pointer;">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <div class="strat-icon"><img src="${logoPath}"></div>
                            <div class="strat-info">
                                <div class="strat-title">${stratName}</div>
                                <div class="strat-desc" style="color: #aaa;">${statusText}</div>
                            </div>
                        </div>
                        <div style="text-align:right;">
                             <div class="strat-title" style="font-size:16px;">$${balance.toFixed(2)}</div>
                        </div>
                    </div>
                 `);
            }
        }
    });
}

function renderActiveStrategies(exchanges, credits = 0) {
    const container = document.getElementById("active-strategies-list");
    if (!container) return;
    container.innerHTML = "";

    const t = translations[currentLang] || translations['en'];

    // Filter for connected exchanges (include Error status to prevent disappearance)
    const active = exchanges ? exchanges.filter(ex => ex.status === "Connected" || ex.status === "Error") : [];

    if (active.length === 0) {
        container.innerHTML = `<div class="fade-in" style="text-align:center; padding:20px; color:#888; font-size:14px;">${t.no_active_strategies || "No active strategies"}</div>`;
        return;
    }

    active.forEach((ex, idx) => {
        let stratName = 'BingBot';
        const exNameLow = ex.name.toLowerCase();
        if (exNameLow === 'okx' || ex.strategy === 'trademax' || ex.strategy === 'cgt') {
            stratName = 'TradeMax';
        } else if (exNameLow === 'bingx') {
            stratName = 'BingBot';
        }
        let typeDesc = 'Spot';
        if (ex.name.toLowerCase() === 'bingx') typeDesc = 'BingX Futures';
        else if (ex.name.toLowerCase() === 'okx') typeDesc = 'OKX Spot';

        const logoPath = `logo_bots/${ex.name.toLowerCase()}.png?v=2`;

        // Status Logic
        let statusText = t.status_active || "Active";
        let statusClass = "text-green";

        if (ex.status === "Error") {
            statusText = t.status_error || "Check API";
            statusClass = "text-red"; // Defined in CSS or inline style needed
        } else if (credits <= 0) {
            statusText = t.status_waiting_topup || "Waiting TopUp";
            statusClass = "text-yellow";
        }

        const html = `
            <div class="strategy-item fade-in" style="animation-delay: ${idx * 0.1}s">
                <div class="strat-icon">
                    <img src="${logoPath}">
                </div>
                <div class="strat-info">
                    <div class="strat-title">${stratName}</div>
                    <div class="strat-desc">${typeDesc}</div>
                </div>
                <div class="strat-status ${statusClass}" style="${statusClass === 'text-red' ? 'color:#FF4D4D;' : ''}">
                    ${statusText}
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}


// --- WIZARD LOGIC ---
// --- OBSOLETE WIZARD FUNCTIONS REMOVED ---
// (setupWizard, filterExchanges, etc.)

// --- RESERVE & TOPUP ---
// --- RESERVE MODAL & FEE INFO ---
let editingExchange = null;
let maxReserve = 0;

function setupReserveModal() {
    const modal = document.getElementById("modal-reserve");
    const btnClose = document.getElementById("btn-close-reserve");
    const btnSave = document.getElementById("btn-save-reserve");
    const btnDisconnect = document.getElementById("btn-disconnect");
    const btnMax = document.getElementById("btn-reserve-max");

    const slider = document.getElementById("inp-reserve-slider");
    const input = document.getElementById("inp-reserve-edit");
    const balanceDisp = document.getElementById("reserve-balance-display");
    const errDisp = document.getElementById("err-reserve-max");

    if (btnClose) btnClose.onclick = () => modal.style.display = "none";

    // Max Button
    if (btnMax) btnMax.onclick = () => {
        // Set to maxReserve
        input.value = maxReserve;
        slider.value = maxReserve;
        validateReserve();
    };

    // Sync Slider -> Input
    slider.oninput = () => {
        input.value = slider.value;
        validateReserve();
    };

    // Sync Input -> Slider
    input.oninput = () => {
        let val = parseFloat(input.value);
        if (isNaN(val)) val = 0;
        // If value exceeds max, update slider to max visually but keep input valid if user is typing
        if (val > maxReserve) slider.value = maxReserve;
        else slider.value = val;
        validateReserve();
    };

    function validateReserve() {
        const val = parseFloat(input.value) || 0;
        if (val > maxReserve) {
            errDisp.style.display = 'block';
            btnSave.classList.add('disabled');
            btnSave.style.pointerEvents = 'none';
            btnSave.style.opacity = '0.5';
        } else {
            errDisp.style.display = 'none';
            btnSave.classList.remove('disabled');
            btnSave.style.pointerEvents = 'auto';
            btnSave.style.opacity = '1';
        }
    }

    if (btnSave) btnSave.onclick = async () => {
        const val = parseFloat(input.value) || 0;
        if (val > maxReserve) return;
        await updateReserve(editingExchange, val);
        modal.style.display = "none";
    };

    if (btnDisconnect) btnDisconnect.onclick = async () => {
        const t = translations[currentLang];
        tg.showPopup({
            title: 'Disconnect?',
            message: t.disconnect_confirm,
            buttons: [
                { id: 'delete', type: 'destructive', text: 'Disconnect' },
                { id: 'cancel', type: 'cancel' }
            ]
        }, async (btnId) => {
            if (btnId === 'delete') {
                await disconnectExchange(editingExchange);
                modal.style.display = "none";
            }
        });
    };

    window.openReserveModal = (exchange, currentVal, balance) => {
        editingExchange = exchange;
        maxReserve = balance || 0;

        balanceDisp.innerText = "$" + maxReserve.toLocaleString('en-US', { minimumFractionDigits: 2 });

        slider.max = maxReserve;
        slider.value = currentVal;
        input.value = currentVal;

        modal.style.display = "flex";
    };

    window.openFeePopup = () => {
        showFeeInfo();
    };

    window.showFeeInfo = () => {
        const t = translations[currentLang];
        tg.showPopup({
            title: t.fee_info_title,
            message: t.fee_info_desc,
            buttons: [{ id: 'topup', type: 'default', text: t.btn_topup_here }, { type: 'ok' }]
        }, (btnId) => {
            if (btnId === 'topup') {
                document.getElementById('modal-topup').style.display = 'flex';
            }
        });
    };
}

// OLD setupTopUpModal - Disabled because we now use CryptAPI with new modal design
// The new modal doesn't have lbl-pay-instr-1, lbl-pay-instr-2, inp-topup-txid, btn-pay
// Instead, it auto-generates addresses via fetchDepositAddress()

/*
function setupTopUpModal() {
    const modal = document.getElementById("modal-topup");
    document.querySelectorAll('[data-action="topup"]').forEach(b => b.onclick = () => {
        // Init instruction text
        const t = translations[currentLang];
        document.getElementById("lbl-pay-instr-1").innerText = t.msg_pay_instruction_1;
        document.getElementById("lbl-pay-instr-2").innerText = t.msg_pay_instruction_2;
        modal.style.display = "flex";
    });

    document.getElementById("btn-close-topup").onclick = () => modal.style.display = "none";

    document.getElementById("btn-pay").onclick = async () => {
        const txId = document.getElementById("inp-topup-txid").value.trim();
        if (!txId) return tg.showAlert("Invalid TxID");
        // Submit TopUp logic...
        const user = tg.initDataUnsafe.user;
        tg.MainButton.showProgress();
        try {
            await fetch(`${API_BASE}/api/topup`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: user.id, tx_id: txId })
            });
            tg.MainButton.hideProgress();
            tg.showAlert("Submitted! Verifying...");
            modal.style.display = "none";
        } catch (e) { tg.MainButton.hideProgress(); }
    };

    window.copyAddress = () => {
        const addr = "0x6c639cac616254232d9c4d51b1c3646132b46c4a";
        navigator.clipboard.writeText(addr);
        tg.showAlert("Address Copied!");
    };
}

// Close setupTopUpModal
setupTopUpModal();
*/

// Modal close handler for new design
function setupModals() {
    const topupModal = document.getElementById('modal-topup');
    if (topupModal) {
        // Close on X button
        const closeBtn = document.getElementById('btn-close-topup');
        if (closeBtn) {
            closeBtn.onclick = () => window.closeModal('modal-topup');
        }

        // Close on backdrop click (optional)
        topupModal.addEventListener('click', (e) => {
            if (e.target === topupModal) window.closeModal('modal-topup');
        });
    }
}

// Global closeModal with animation
window.closeModal = function (id) {
    const m = document.getElementById(id);
    if (m) {
        const content = m.querySelector('.sheet-content');

        // Add closing class for animation
        if (content) content.classList.add('closing');
        m.classList.add('closing');

        // Wait for animation to finish
        setTimeout(() => {
            m.style.display = 'none';
            m.classList.remove('sheet-mode');
            m.classList.remove('closing');
            if (content) content.classList.remove('closing');
        }, 300); // Match CSS animation duration
    }
};

// === WITHDRAW FUNDS FUNCTIONS ===
window.openWithdrawModal = function () {
    const modal = document.getElementById('modal-withdraw');
    if (!modal) return;

    // Get balance from settings display
    const balanceEl = document.getElementById('credits-bal-settings');
    const balance = balanceEl ? parseFloat(balanceEl.innerText) : 0;

    // Update balance display in modal
    const balanceDisplay = document.getElementById('withdraw-available-balance');
    if (balanceDisplay) {
        balanceDisplay.innerText = `${balance.toFixed(2)} USDT`;
    }

    // Clear inputs
    document.getElementById('withdraw-amount').value = '';
    document.getElementById('withdraw-wallet').value = '';

    // Show modal
    modal.classList.add('sheet-mode');
    modal.style.display = 'flex';
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
};

window.closeWithdrawModal = function () {
    window.closeModal('modal-withdraw');
};

window.setWithdrawMax = function () {
    const balanceEl = document.getElementById('credits-bal-settings');
    const balance = balanceEl ? parseFloat(balanceEl.innerText) : 0;
    document.getElementById('withdraw-amount').value = balance.toFixed(2);
};

window.submitWithdrawRequest = async function () {
    const amountInput = document.getElementById('withdraw-amount');
    const walletInput = document.getElementById('withdraw-wallet');
    const amount = parseFloat(amountInput.value);
    const wallet = walletInput.value.trim();

    const t = translations[currentLang] || translations['en'];

    // Validate amount
    if (!amount || amount <= 0) {
        alert(t.err_invalid_amount);
        return;
    }

    // Check balance
    const balanceEl = document.getElementById('credits-bal-settings');
    const balance = balanceEl ? parseFloat(balanceEl.innerText) : 0;

    if (amount > balance) {
        alert(t.err_insufficient_balance);
        return;
    }

    // Validate wallet address (0x + 40 hex chars = 42 total)
    if (!wallet.startsWith('0x') || wallet.length !== 42) {
        alert(t.err_invalid_wallet);
        return;
    }

    // Submit request
    try {
        const user_id = tg.initDataUnsafe?.user?.id;
        if (!user_id) {
            tg.showAlert("Please open this app from Telegram bot.");
            return;
        }
        const response = await fetch(`${API_BASE}/api/withdraw`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id, amount, wallet_address: wallet })
        });

        const data = await response.json();

        if (data.success) {
            alert(t.withdraw_success);
            // Update balance in UI
            if (balanceEl) {
                balanceEl.innerText = (balance - amount).toFixed(2);
            }
            // Close modal
            closeWithdrawModal();
            // Refresh data
            const userId = tg.initDataUnsafe?.user?.id;
            if (!userId) {
                tg.showAlert("Please open this app from Telegram bot.");
                return;
            }
            await fetchUserData(userId);
        } else {
            alert(data.message || 'Error submitting withdrawal request');
        }
    } catch (error) {
        console.error('Withdrawal error:', error);
        alert('Failed to submit withdrawal request. Please try again.');
    }
};

function setupWithdrawButton() {
    const withdrawBtn = document.getElementById('btn-withdraw-funds');

    if (withdrawBtn) {
        withdrawBtn.onclick = () => {
            openWithdrawModal();
        };
    }
}

// === ACTION BUTTONS & BOTTOM SHEET ===
function setupActionButtons() {
    // Top Up Card
    const topUpCard = document.querySelector('.action-card[data-action="topup"]');

    if (topUpCard) {
        topUpCard.addEventListener('click', () => {
            const modal = document.getElementById('modal-topup');

            if (modal) {
                modal.classList.add('sheet-mode');
                modal.style.display = 'flex';
                fetchDepositAddress();
            }
        });
    }

    const ctCard = document.getElementById('btn-copy-trading');
    if (ctCard) {
        ctCard.addEventListener('click', () => {
            const modal = document.getElementById('modal-copytrading');
            if (modal) {
                modal.style.display = 'flex';
                // Show market type selection first
                if (typeof showCTStep === 'function') showCTStep('market-type');

                if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            }
        });
    }

    // Analyze Chart Card
    const analyzeCard = document.querySelector('.action-card[data-action="analyze"]');

    if (analyzeCard) {
        analyzeCard.onclick = () => {
            const modal = document.getElementById('modal-analyzer');
            if (modal) {
                modal.style.display = 'flex';
                if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            }
        };
    }

    // View All Strategies Button (Dashboard)
    const viewAllBtn = document.querySelector('.view-all');
    if (viewAllBtn) {
        viewAllBtn.onclick = () => {
            console.log('[DEBUG] View All clicked');
            const exchangeTab = document.querySelector('.bottom-nav-bar .nav-item[data-target="exchanges"]');
            if (exchangeTab) {
                exchangeTab.click(); // Switch tab
            } else {
                console.error('[ERROR] Exchanges tab not found');
            }
            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        };
    }
}

// === STRATEGY SETTINGS MODAL (Top Level) ===
let currentStrategySettings = null; // Stores {name, reserve, risk, balance}

function setupStrategySettings() {
    // 1. Risk Slider
    const riskSlider = document.getElementById("st-set-risk");
    if (riskSlider) {
        riskSlider.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            document.getElementById("st-set-risk-val").innerText = val + "%";
            // Color logic
            const label = document.getElementById("st-set-risk-val");
            if (val <= 2) label.style.color = "#06D6A0"; // Green
            else if (val <= 4) label.style.color = "#FFD166"; // Yellow
            else label.style.color = "#FF4D4D"; // Red
        });
    }

    // 2. Capital Slider & Input Sync
    const capSlider = document.getElementById("st-set-reserve-slider");
    const capInput = document.getElementById("st-set-reserve");

    if (capSlider && capInput) {
        // Slider -> Input
        capSlider.addEventListener("input", (e) => {
            capInput.value = e.target.value;
        });

        // Input -> Slider
        capInput.addEventListener("input", (e) => {
            let val = parseFloat(e.target.value);
            if (isNaN(val)) val = 0;
            capSlider.value = val;
        });
    }
}

// Call this in DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
    setupStrategySettings();
});

// Helper for MAX button
window.setCapitalMax = function () {
    if (!currentStrategySettings) return;
    const maxVal = currentStrategySettings.balance || 0;

    const input = document.getElementById("st-set-reserve");
    const slider = document.getElementById("st-set-reserve-slider");

    if (input) input.value = maxVal.toFixed(2);
    if (slider) slider.value = maxVal;
};

// UPDATED SIGNATURE: Accept balance and statusText
function openStrategySettings(name, reserve, risk, isActive, balance = 0, statusText = "Active") {
    console.log('[DEBUG] openStrategySettings called:', { name, reserve, risk, isActive, balance, statusText });
    currentStrategySettings = { name, reserve, risk, balance };

    // 1. Populate Info
    document.getElementById("st-set-name").innerText = name.charAt(0).toUpperCase() + name.slice(1);

    const icon = document.getElementById("st-set-icon").querySelector("img");
    icon.src = `logo_bots/${name.toLowerCase()}.png?v=2`;

    // Status Logic
    const statusEl = document.getElementById("st-set-status");
    statusEl.innerText = statusText;

    if (statusText.includes("Waiting")) {
        statusEl.style.color = "#FFD166"; // Yellow
        statusEl.style.background = "rgba(255, 209, 102, 0.1)";
    } else if (isActive) {
        statusEl.style.color = "#06D6A0"; // Green
        statusEl.style.background = "rgba(6, 214, 160, 0.1)";
    } else {
        statusEl.style.color = "#FF4D4D"; // Red
        statusEl.style.background = "rgba(255, 77, 77, 0.1)";
    }

    // 2. Populate Inputs
    document.getElementById("st-set-reserve").value = reserve;

    // Update Balance Text
    document.getElementById("st-set-balance").innerText = `Available: ${balance.toFixed(2)} USDT`;

    // Configure Capital Slider Max
    const capSlider = document.getElementById("st-set-reserve-slider");
    if (capSlider) {
        capSlider.max = (balance > 0) ? balance : (reserve * 2 || 1000); // Set sane max
        capSlider.value = reserve;
    }

    // Risk Slider
    const riskVal = risk || 1.0;
    const slider = document.getElementById("st-set-risk");
    slider.value = riskVal;
    document.getElementById("st-set-risk-val").innerText = riskVal + "%";

    // 3. Show Modal
    const modal = document.getElementById("modal-strategy-settings");
    console.log('[DEBUG] Modal element:', modal);
    if (modal) {
        modal.classList.add('sheet-mode');
        modal.style.display = "flex";

        // Exact logic requested by user
        const content = modal.querySelector('.modal-content');
        if (content) {
            content.style.height = '85vh'; // Use viewport percentage
            content.style.overflowY = 'auto'; // Enable scrolling
            content.style.transition = 'height 0.3s ease'; // Smooth transition
        }

        if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
    } else {
        console.error('[ERROR] Modal not found!');
    }
}

function closeStrategySettings() {
    // Use global closeModal to trigger slide-down animation
    if (window.closeModal) {
        window.closeModal("modal-strategy-settings");
    } else {
        const modal = document.getElementById("modal-strategy-settings");
        if (modal) modal.style.display = "none";
    }
}

async function saveStrategySettings() {
    if (!currentStrategySettings) return;

    const reserve = parseFloat(document.getElementById("st-set-reserve").value) || 0;
    const risk = parseFloat(document.getElementById("st-set-risk").value) || 1.0;
    const user = tg.initDataUnsafe.user;

    const btn = document.querySelector("#modal-strategy-settings .btn-primary");
    const originalText = btn.innerText;
    btn.innerText = "Saving...";

    try {
        const res = await fetch(`${API_BASE}/api/update-params`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange: currentStrategySettings.name,
                reserve: reserve,
                risk_pct: risk
            })
        });

        if (res.ok) {
            closeStrategySettings();
            showToast(getTranslation('toast_changes_applied') || "Changes Applied");
            if (user.id) fetchUserData(user.id); // Refresh UI
        } else {
            alert("Failed to save settings");
        }
    } catch (e) {
        console.error(e);
        alert("Error saving settings");
    } finally {
        btn.innerText = originalText;
    }
}

async function disconnectStrategy() {
    if (!currentStrategySettings) return;

    const user = tg.initDataUnsafe.user;
    const t = translations[currentLang];

    // Show confirmation popup
    tg.showPopup({
        title: t.btn_disconnect || 'Disconnect Strategy',
        message: 'Are you sure you want to disconnect this strategy? All settings will be removed.',
        buttons: [
            { id: 'disconnect', type: 'destructive', text: t.btn_disconnect || 'Disconnect' },
            { id: 'cancel', type: 'cancel', text: 'Cancel' }
        ]
    }, async (btnId) => {
        if (btnId === 'disconnect') {
            try {
                const res = await fetch(`${API_BASE}/api/disconnect`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: user.id,
                        exchange: currentStrategySettings.name
                    })
                });

                if (res.ok) {
                    closeStrategySettings();
                    showToast(getTranslation('toast_strategy_disconnected') || "Strategy Disconnected");
                    if (user.id) fetchUserData(user.id); // Refresh UI
                } else {
                    tg.showAlert("Failed to disconnect strategy. Please try again.");
                }
            } catch (e) {
                console.error(e);
                tg.showAlert("Error disconnecting strategy.");
            }
        }
    });
}

function showToast(msg) {
    const toast = document.getElementById("toast"); // Ensure index.html has this
    if (!toast) {
        console.error('[ERROR] Toast element not found');
        return;
    }
    toast.innerText = msg;
    toast.style.display = "block";
    setTimeout(() => {
        toast.style.display = "none";
    }, 2000);
}




async function fetchDepositAddress() {
    const addrEl = document.getElementById('deposit-address-text');
    if (!addrEl) return;

    addrEl.innerText = "Generating address...";
    addrEl.style.opacity = "0.7";

    try {
        const uid = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) ? tg.initDataUnsafe.user.id : 0;

        const res = await fetch(`${API_BASE}/api/create_payment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: uid })
        });
        const data = await res.json();

        if (data.status === 'ok') {
            addrEl.innerText = data.address;
            addrEl.style.opacity = "1";
        } else {
            addrEl.innerText = "Error: " + (data.msg || "Service Unavailable");
        }
    } catch (error) {
        console.error(error);
    }
}

// === COPY TRADING MODAL ===
// === COPY TRADING MODAL ===
let selectedMarketType = null; // Track selected market type: 'futures' or 'spot'

function setupCopyTradingModal() {
    const modal = document.getElementById('modal-copytrading');
    if (!modal) {
        return;
    }

    // Event Delegation for all clicks in the modal
    modal.onclick = (e) => {
        // Handle market type selection
        const marketBtn = e.target.closest('.market-type-selector');
        if (marketBtn) {
            const marketType = marketBtn.dataset.market;
            selectedMarketType = marketType;

            // Show strategy step
            showCTStep('strategy');

            // Filter strategies based on market type
            filterStrategiesByMarket(marketType);

            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            return;
        }

        // Handle strategy selection
        const strategyBtn = e.target.closest('.strategy-selector-btn');
        if (strategyBtn) {
            const strategy = strategyBtn.dataset.strategy;
            const exchange = strategyBtn.dataset.exchange;

            if (exchange === 'bingx') showCTStep('bingx-api');
            else if (exchange === 'okx') showCTStep('okx-api');

            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        }
    };
}

// Filter strategies based on market type
function filterStrategiesByMarket(marketType) {
    const bingbotCard = document.querySelector('.strategy-selector-btn[data-strategy="bingbot"]');
    const trademaxCard = document.querySelector('.strategy-selector-btn[data-strategy="trademax"]');

    if (marketType === 'futures') {
        // Show only BingBot
        if (bingbotCard) bingbotCard.style.display = 'flex';
        if (trademaxCard) trademaxCard.style.display = 'none';
    } else if (marketType === 'spot') {
        // Show only TradeMax
        if (bingbotCard) bingbotCard.style.display = 'none';
        if (trademaxCard) trademaxCard.style.display = 'flex';
    }
}


function showCTStep(stepName) {
    const steps = document.querySelectorAll('.ct-step');
    steps.forEach(step => step.style.display = 'none');

    const targetId = `ct-step-${stepName}`;
    const targetStep = document.getElementById(targetId);

    // Dynamic Height Adjustment
    const modalContent = document.querySelector('#modal-copytrading .modal-content');
    if (modalContent) {
        if (stepName === 'bingx-api' || stepName === 'okx-api' || stepName === 'coin-select' || stepName === 'coin-config') {
            // Expand for API forms and coin selection/config
            modalContent.style.height = '85vh'; // Use viewport percentage
            modalContent.style.overflowY = 'auto'; // Enable scrolling for forms, but config handles its own
            modalContent.style.transition = 'height 0.3s ease'; // Smooth transition

            if (stepName === 'coin-config') {
                modalContent.style.overflowY = 'hidden'; // Config step manages its own scroll
            }
        } else {
            // Reset for strategy selection (or other small steps)
            modalContent.style.height = '580px';
            modalContent.style.overflowY = 'hidden';
        }
    }

    if (targetStep) {
        if (stepName === 'coin-config') {
            targetStep.style.display = 'flex';
        } else {
            targetStep.style.display = 'block';
        }
    }
}

// Helper for Copying Text (IP Address)
function copyText(text) {
    if (text) {
        navigator.clipboard.writeText(text).then(() => {
            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            // Show toast manually if needed, or rely on UI feedback
            const toast = document.getElementById('toast-notification');
            if (toast) {
                toast.innerText = "Copied to Clipboard!";
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2000);
            }
        }).catch(err => {
            console.error('Failed to copy: ', err);
            // Fallback
            const textArea = document.createElement("textarea");
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                const toast = document.getElementById('toast-notification');
                if (toast) {
                    toast.innerText = "Copied to Clipboard!";
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2000);
                }
            } catch (err) {
                console.error('Fallback copy failed', err);
            }
            document.body.removeChild(textArea);
        });
    }
}

function closeCopyTradingModal() {
    const modal = document.getElementById('modal-copytrading');
    if (modal) {
        modal.style.display = 'none';
        // Reset to market type selection
        showCTStep('market-type');
        selectedMarketType = null;
        // Clear form inputs
        document.getElementById('bingx-api-key').value = '';
        document.getElementById('bingx-secret-key').value = '';
        document.getElementById('bingx-capital').value = '';
        document.getElementById('okx-api-key').value = '';
        document.getElementById('okx-secret-key').value = '';
        document.getElementById('okx-passphrase').value = '';
        document.getElementById('okx-capital').value = '';
    }
}

async function submitBingXAPI() {
    const apiKey = document.getElementById('bingx-api-key').value.trim();
    const secretKey = document.getElementById('bingx-secret-key').value.trim();
    const capital = parseFloat(document.getElementById('bingx-capital').value);

    // Allow 0 capital (means no trading yet)
    if (!apiKey || !secretKey || isNaN(capital)) {
        alert('Please fill API rules correctly');
        return;
    }

    try {
        const user = tg.initDataUnsafe.user;
        const response = await fetch(`${API_BASE}/api/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange: 'bingx',
                strategy: 'ratner',
                api_key: apiKey,
                secret: secretKey,
                password: '',
                reserve: capital
            })
        });

        const data = await response.json();
        if (data.status === 'ok') {
            showToast('BingX Connected!');
            closeCopyTradingModal();
            await fetchUserData(user.id);
        } else {
            console.error(data.message || 'Connection failed');
        }
    } catch (error) {
        console.error(error);
    }
}

// ===========================
// MULTI-COIN CONFIGURATION
// ===========================

// Global state for coin selection
let selectedCoins = new Set();
let okxApiCredentials = null;

// Proceed to coin selection step
function proceedToCoinSelection() {
    const apiKey = document.getElementById('okx-api-key').value.trim();
    const secretKey = document.getElementById('okx-secret-key').value.trim();
    const passphrase = document.getElementById('okx-passphrase').value.trim();

    if (!apiKey || !secretKey || !passphrase) {
        alert('Please fill in all API credentials');
        return;
    }

    // Store credentials temporarily
    okxApiCredentials = { apiKey, secretKey, passphrase };

    // Reset coin selection
    selectedCoins.clear();
    document.querySelectorAll('.coin-card').forEach(card => {
        card.classList.remove('selected');
    });
    document.getElementById('btn-coin-next').disabled = true;

    // Show coin selection step
    showCTStep('coin-select');
}

// Toggle coin selection
function toggleCoin(symbol) {
    const card = document.querySelector(`.coin-card[data-symbol="${symbol}"]`);

    if (selectedCoins.has(symbol)) {
        selectedCoins.delete(symbol);
        card.classList.remove('selected');
    } else {
        selectedCoins.add(symbol);
        card.classList.add('selected');
    }

    // Enable/disable next button
    document.getElementById('btn-coin-next').disabled = selectedCoins.size === 0;
}

// Proceed to coin configuration
function proceedToCoinConfig() {
    if (selectedCoins.size === 0) return;

    // Render configuration forms for each selected coin
    const configList = document.getElementById('coin-config-list');
    configList.innerHTML = '';

    const coinDetails = {
        'BTC/USDT': { name: 'Bitcoin', img: 'bitcoin.png' },
        'ETH/USDT': { name: 'Ethereum', img: 'ethereum.png' },
        'BNB/USDT': { name: 'BNB', img: 'bnb.png' },
        'OKB/USDT': { name: 'OKB', img: 'okb.png' }
    };

    selectedCoins.forEach(symbol => {
        const details = coinDetails[symbol];
        const html = `
            <div class="coin-config-item">
                <div class="coin-config-header">
                    <img src="coin_img/${details.img}" width="32" height="32">
                    <div>
                        <div class="coin-name">${details.name}</div>
                        <div class="coin-symbol">${symbol}</div>
                    </div>
                </div>
                
                <div class="ct-input-group">
                    <label class="ct-label" data-i18n="trading_capital_usdt">Trading Capital (USDT)</label>
                    <input type="number" id="capital-${symbol}" class="ct-input" 
                           data-i18n-placeholder="minimum_5_usdt" placeholder="Amount (e.g. 100)" step="0.01" value="100">
                    <div class="validation-error" id="error-${symbol}"></div>
                </div>
                
                <div class="ct-input-group">
                    <label class="ct-label" data-i18n="risk_per_trade_pct">Risk per Trade (%)</label>
                    <input type="number" id="risk-${symbol}" class="ct-input" 
                           placeholder="1.0" step="0.1" min="0.1" max="10" value="1.0">
                </div>
            </div>
        `;
        configList.insertAdjacentHTML('beforeend', html);
    });

    showCTStep('coin-config');
}

// Submit OKX with coin configurations
async function submitOKXWithCoins() {
    if (!okxApiCredentials) {
        alert('API credentials missing');
        return;
    }

    // Collect coin configurations
    const coins = [];
    let totalCapital = 0;
    let hasErrors = false;

    selectedCoins.forEach(symbol => {
        const capitalInput = document.getElementById(`capital-${symbol}`);
        const riskInput = document.getElementById(`risk-${symbol}`);
        const errorDiv = document.getElementById(`error-${symbol}`);

        const capital = parseFloat(capitalInput.value);
        const risk = parseFloat(riskInput.value);

        // Validate
        errorDiv.classList.remove('show');
        if (isNaN(capital) || capital < 0) {
            errorDiv.textContent = 'Invalid amount';
            errorDiv.classList.add('show');
            hasErrors = true;
            return;
        }

        if (isNaN(risk) || risk < 0.1 || risk > 10) {
            errorDiv.textContent = 'Risk must be between 0.1% and 10%';
            errorDiv.classList.add('show');
            hasErrors = true;
            return;
        }

        coins.push({ symbol, capital, risk });
        totalCapital += capital;
    });

    if (hasErrors) return;

    try {
        const user = tg.initDataUnsafe.user;
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = 'Connecting...';

        // First, connect OKX exchange
        const connectResponse = await fetch(`${API_BASE}/api/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange: 'okx',
                strategy: 'cgt',
                api_key: okxApiCredentials.apiKey,
                secret: okxApiCredentials.secretKey,
                password: okxApiCredentials.passphrase,
                reserve: totalCapital  // Total allocation
            })
        });

        const connectData = await connectResponse.json();
        if (connectData.status !== 'ok') {
            alert(connectData.detail || 'Connection failed');
            btn.disabled = false;
            btn.textContent = 'Connect OKX';
            return;
        }

        // Then, save coin configurations
        const coinResponse = await fetch(`${API_BASE}/api/save_coin_configs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange: 'okx',
                coins: coins
            })
        });

        const coinData = await coinResponse.json();
        if (!coinData.success) {
            alert(coinData.message || 'Failed to save coin configurations');
            btn.disabled = false;
            btn.textContent = 'Connect OKX';
            return;
        }

        // Success!
        showToast((getTranslation('toast_okx_connected') || 'OKX Connected') + ` (${coins.length} coins)`);
        closeCopyTradingModal();

        // Clear state
        selectedCoins.clear();
        okxApiCredentials = null;

        // Refresh UI with delay to ensure DB write
        setTimeout(async () => {
            await fetchUserData(user.id);
        }, 800);

    } catch (error) {
        console.error(error);
        event.target.disabled = false;
        event.target.textContent = 'Connect OKX';
    }
}

// Edit existing coin configuration
let editingCoin = null;

function editCoinConfig(exchange, symbol, currentCapital, currentRisk) {
    const modal = document.getElementById('modal-edit-coin');
    if (!modal) return;

    editingCoin = { exchange, symbol };

    // Set Values
    document.getElementById('ec-symbol').innerText = symbol;
    document.getElementById('ec-exchange').innerText = exchange.toUpperCase();
    document.getElementById('ec-capital').value = currentCapital;
    document.getElementById('ec-risk').value = currentRisk;

    // Set Icon
    const iconMap = {
        'BTC/USDT': 'bitcoin.png',
        'ETH/USDT': 'ethereum.png',
        'BNB/USDT': 'bnb.png',
        'OKB/USDT': 'okb.png'
    };
    const imgName = iconMap[symbol] || 'usdt_bep_icon.svg';
    const src = imgName.includes('svg') ? imgName : `coin_img/${imgName}`;
    document.querySelector('#ec-icon img').src = src;

    modal.style.display = 'flex';
    applyTranslations();
}

function closeEditCoinModal() {
    document.getElementById('modal-edit-coin').style.display = 'none';
    editingCoin = null;
}

async function submitEditCoin() {
    if (!editingCoin) return;

    const user = tg.initDataUnsafe.user;
    const newCapital = parseFloat(document.getElementById('ec-capital').value);
    const newRisk = parseFloat(document.getElementById('ec-risk').value);

    if (isNaN(newCapital) || isNaN(newRisk)) {
        alert("Invalid values");
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/update_coin_config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange: editingCoin.exchange.toLowerCase(),
                symbol: editingCoin.symbol,
                capital: newCapital,
                risk: newRisk
            })
        });

        const data = await res.json();
        if (data.success) {
            showToast(getTranslation('toast_coin_updated') || 'Coin updated');
            closeEditCoinModal();
            fetchUserData(user.id);
        } else {
            let msg = data.message || data.detail || 'Update failed';
            if (typeof msg === 'object') msg = JSON.stringify(msg);
            alert(msg);
        }
    } catch (e) {
        console.error(e);
        alert('Error updating coin');
    }
}

async function deleteEditCoin() {
    if (!editingCoin) return;

    if (!confirm("Are you sure you want to remove this coin?")) return;

    try {
        const user = tg.initDataUnsafe.user;
        const res = await fetch(`${API_BASE}/api/delete_coin_config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange: editingCoin.exchange.toLowerCase(),
                symbol: editingCoin.symbol
            })
        });

        const data = await res.json();

        // Handle flexible success response (status: 'ok' or success: true)
        if (data.status === 'ok' || data.success === true) {
            showToast(getTranslation('toast_coin_removed') || 'Coin removed');
            closeEditCoinModal();

            // Check if any coins remain for this exchange
            const checkRes = await fetch(`${API_BASE}/api/get_coin_configs?user_id=${user.id}&exchange=${editingCoin.exchange}`);
            const checkData = await checkRes.json();

            if (!checkData.coins || checkData.coins.length === 0) {
                // No coins left -> Disconnect exchange
                await disconnectExchange(editingCoin.exchange);
                showToast(getTranslation('toast_exchange_disconnected') || 'Exchange disconnected');
            } else {
                // Refresh list if exchange still active
                openCoinManagement(user.id, editingCoin.exchange);
                // Also refresh main user data
                setTimeout(() => fetchUserData(user.id), 500);
            }

        } else {
            alert(data.message || 'Removal failed');
        }
    } catch (error) {
        console.error(error);
    }
}

// Add new coin to existing exchange
function addNewCoin(exchange) {
    // Show coin selector popup
    tg.showPopup({
        title: 'Add Coin',
        message: 'This feature will open the coin selector. For now, please use the copytrading modal to add coins.',
        buttons: [{ id: 'ok', type: 'ok', text: 'OK' }]
    });

    // TODO: Implement inline coin addition
    // For now, user should go through the copytrading modal
}

// Toast Notification
function showToast(message) {
    const toast = document.getElementById('toast-notification');
    if (!toast) return;

    toast.innerText = message;
    toast.classList.add('show');

    // Haptic feedback
    if (window.tg && tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }

    // Hide after 2 seconds
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);
}

// Ensure copyAddress is globally available
window.copyAddress = () => {
    const text = document.getElementById('deposit-address-text').innerText;
    if (!text || text.includes("...")) return;
    navigator.clipboard.writeText(text);

    // Show Toast
    showToast(getTranslation('toast_address_copied') || "Address Copied");
};

// --- TABS & UTILS ---
function setupTabs() {
    const pads = document.querySelectorAll('.nav-item');
    const pages = document.querySelectorAll('.page');

    pads.forEach(pad => {
        pad.addEventListener('click', () => {
            const target = pad.dataset.target;

            // UI Update (CSS handles animation now)
            pads.forEach(p => p.classList.remove('active'));
            pad.classList.add('active');

            // Page Transition
            pages.forEach(p => {
                p.style.opacity = '0';
                setTimeout(() => { p.classList.remove('active'); }, 200); // Wait for fade out
            });

            setTimeout(() => {
                const tEl = document.getElementById(target);
                if (tEl) {
                    tEl.classList.add('active');
                    // Small delay to allow display:block to apply before opacity
                    requestAnimationFrame(() => {
                        tEl.style.opacity = '1';
                    });
                }
            }, 200);

            if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        });
    });
}

function setupLanguageSelector() {
    document.querySelectorAll('.lang-btn').forEach(btn =>
        btn.onclick = async () => {
            const lang = btn.dataset.lang;
            const user = tg.initDataUnsafe.user;
            await fetch(`${API_BASE} /api/language`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: user.id, language: lang })
            });
            setLanguage(lang);
        }
    );
}

function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = "$" + (progress * end).toLocaleString('en-US', { minimumFractionDigits: 2 });
        if (progress < 1) window.requestAnimationFrame(step);
    };
    window.requestAnimationFrame(step);
}

async function updateReserve(exchange, amount) {
    const user = tg.initDataUnsafe.user;
    if (!user) return;
    tg.MainButton.showProgress();
    try {
        await fetch(`${API_BASE} /api/reserve`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id, exchange: exchange, reserve: amount })
        });
        tg.MainButton.hideProgress();
        fetchUserData(user.id);
    } catch (e) { tg.MainButton.hideProgress(); console.error(e); }
}

async function disconnectExchange(exchange) {
    const user = tg.initDataUnsafe.user;
    if (!user) return;
    tg.MainButton.showProgress();
    try {
        await fetch(`${API_BASE} /api/disconnect`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id, exchange: exchange })
        });
        tg.MainButton.hideProgress();
        fetchUserData(user.id);
    } catch (e) { tg.MainButton.hideProgress(); console.error(e); }
}

// --- INITIALIZATION ---
window.onload = function () {
    console.log('[DEBUG] window.onload fired');
    if (window.tg) {
        tg.ready();
        tg.expand();
    }

    // Auth check
    const user = (window.tg && tg.initDataUnsafe) ? tg.initDataUnsafe.user : null;
    if (user) {
        // Load Data
        if (typeof fetchUserData === 'function') fetchUserData(user.id);

        // Start Polling (if defined)
        if (typeof startPolling === 'function') startPolling();
    }

    if (typeof setupTabs === 'function') setupTabs();
    if (typeof setupActionButtons === 'function') setupActionButtons();
    if (typeof setupLanguageSelector === 'function') setupLanguageSelector();
    if (typeof setupModals === 'function') setupModals();
    if (typeof setupWithdrawButton === 'function') setupWithdrawButton();
    if (typeof setupCopyTradingModal === 'function') setupCopyTradingModal();
    if (typeof setupReferralButton === 'function') setupReferralButton();

    // GLOBAL DEBUG CLICK LISTENER
    document.addEventListener('click', (e) => {
        console.log('[GLOBAL CLICK DEBUG]', e.target, 'Closest ID:', e.target.id || e.target.closest('[id]')?.id);
    });

    // SPLASH SCREEN HANDLING
    const splash = document.getElementById('splash-screen');
    if (splash) {
        // Click listener
        splash.addEventListener('click', () => {
            if (typeof window.dismissSplash === 'function') window.dismissSplash();
            else splash.style.display = 'none'; // Fallback
        });

        // Auto-open after 5 seconds (User Feature Request)
        setTimeout(() => {
            if (splash.style.display !== 'none') {
                if (typeof window.dismissSplash === 'function') window.dismissSplash();
                else splash.style.display = 'none';
            }
        }, 5000);
    }
};


// === ANALYZER LOGIC ===
let currentAnalysisContext = null;



window.openAnalyzer = function () {
    const modal = document.getElementById('modal-analyzer');
    if (!modal) {
        console.error('Modal analyzer not found');
        return;
    }
    modal.style.display = 'flex'; // Sheet mode display

    // Reset state
    const uploadStep = document.getElementById('analyzer-step-upload');
    const loadingStep = document.getElementById('analyzer-step-loading');
    const resultStep = document.getElementById('analyzer-step-result');
    const input = document.getElementById('chart-input');
    const explainBox = document.getElementById('explanation-text');

    if (uploadStep) uploadStep.style.display = 'block';
    if (loadingStep) loadingStep.style.display = 'none';
    if (resultStep) resultStep.style.display = 'none';
    if (input) input.value = '';
    if (explainBox) {
        explainBox.style.display = 'none';
        explainBox.innerText = '';
    }
    currentAnalysisContext = null;

    if (window.tg && window.tg.HapticFeedback) window.tg.HapticFeedback.impactOccurred('light');
};

window.closeAnalyzer = function () {
    const modal = document.getElementById('modal-analyzer');
    if (modal) modal.style.display = 'none'; // Sheet mode compatibility
};

window.handleChartUpload = async function (input) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];
    // Safe access to user id
    const user = (window.tg && window.tg.initDataUnsafe && window.tg.initDataUnsafe.user) ? window.tg.initDataUnsafe.user : { id: 0 };

    // Show Loading
    document.getElementById('analyzer-step-upload').style.display = 'none';
    document.getElementById('analyzer-step-loading').style.display = 'block';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', user.id);

    try {
        const response = await fetch(`${API_BASE}/api/analyze?user_id=${user.id}`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.status === 'error') {
            alert(data.msg || 'Analysis failed');
            window.openAnalyzer(); // Reset
            return;
        }

        // Render Result
        const plan = data.plan;

        const tickerEl = document.getElementById('res-ticker');
        if (tickerEl) tickerEl.innerText = (data.ticker || 'UNKNOWN') + " (" + (data.timeframe || '') + ")";

        const viewEl = document.getElementById('res-view');
        if (viewEl) {
            viewEl.className = 'res-view';
            if (plan.view === 'long') {
                viewEl.classList.add('view-long');
                viewEl.innerText = 'LONG';
            } else if (plan.view === 'short') {
                viewEl.classList.add('view-short');
                viewEl.innerText = 'SHORT';
            } else {
                viewEl.classList.add('view-neutral');
                viewEl.innerText = 'NEUTRAL';
            }
        }

        const tfEl = document.getElementById('res-tf');
        if (tfEl) tfEl.innerText = data.timeframe;

        const confEl = document.getElementById('res-conf');
        if (confEl) confEl.innerText = Math.round((plan.confidence || 0) * 100) + "%";

        const entryEl = document.getElementById('res-entry');
        if (entryEl) entryEl.innerText = plan.entry_zone ? plan.entry_zone.join(' - ') : '-';

        const targetEl = document.getElementById('res-target');
        if (targetEl) targetEl.innerText = plan.targets ? plan.targets[0] : '-';

        const stopEl = document.getElementById('res-stop');
        if (stopEl) stopEl.innerText = plan.stop || '-';

        const notesEl = document.getElementById('res-notes');
        if (notesEl) notesEl.innerText = plan.notes || 'No description available.';

        currentAnalysisContext = data.context;

        // Show Result
        document.getElementById('analyzer-step-loading').style.display = 'none';
        document.getElementById('analyzer-step-result').style.display = 'block';

        if (window.tg && window.tg.HapticFeedback) window.tg.HapticFeedback.notificationOccurred('success');

    } catch (e) {
        console.error(e);
        alert("Network Error: " + e.message);
        window.openAnalyzer();
    }
};

// Markdown parser for explanation text
function parseMarkdown(text) {
    if (!text) return '';

    let html = text;

    // Convert ### Headers to styled divs
    html = html.replace(/###\s+(.+)/g, '<div class="exp-heading">$1</div>');

    // Convert **bold** to <strong>
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Convert numbered lists (1. 2. 3.) to styled list items
    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<div class="exp-list-item"><span class="exp-num">$1.</span> $2</div>');

    // Convert line breaks to <br> for paragraphs
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/\n/g, '<br>');

    return html;
}

window.explainSignal = async function () {
    if (!currentAnalysisContext) return;

    const btn = document.querySelector('.explain-btn');
    const box = document.getElementById('explanation-text');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-small"></span> Thinking...`;
    }

    try {
        const user = (window.tg && window.tg.initDataUnsafe && window.tg.initDataUnsafe.user) ? window.tg.initDataUnsafe.user : { id: 0 };
        const response = await fetch(`${API_BASE}/api/explain`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id, context: currentAnalysisContext })
        });

        const data = await response.json();

        if (box) {
            box.style.display = 'block';
            // Parse markdown and render as HTML
            box.innerHTML = parseMarkdown(data.explanation || "Could not generate explanation.");
        }

    } catch (e) {
        alert("Explain Error: " + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `Explain Logic`;
        }
    }
};





// === REFERRAL SYSTEM ===

// Open referral modal and fetch stats
function openReferralModal() {
    const modal = document.getElementById('modal-referral');
    if (modal) {
        modal.style.display = 'flex';
        fetchReferralStats();

        if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
    }
}

// Close referral modal
function closeReferralModal() {
    const modal = document.getElementById('modal-referral');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Fetch referral statistics from backend
// Fetch referral statistics from backend
// Fetch referral statistics from backend
async function fetchReferralStats() {
    try {
        let userId = 0;

        // Try getting user from Telegram WebApp
        if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
            userId = tg.initDataUnsafe.user.id;
        }

        // Fallback: Check URL parameters (common in browser testing)
        if (!userId || userId === 0) {
            const urlParams = new URLSearchParams(window.location.search);
            const urlUserId = urlParams.get('user_id');
            if (urlUserId) {
                userId = parseInt(urlUserId);
            }
        }

        if (!userId || userId === 0) {
            console.warn('[WARN] No valid user_id found. Cannot fetch referral stats.');
            document.getElementById('referral-link').innerText = 'Please open in Telegram';
            return;
        }

        const response = await fetch(`${API_BASE}/api/referral_stats`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });

        if (!response.ok) {
            throw new Error(`Server returned fail status: ${response.status}`);
        }

        const data = await response.json();

        // Update UI
        document.getElementById('referral-link').innerText = data.referral_link || 'https://t.me/bot?start=...';
        document.getElementById('level-1-count').innerText = `${data.level_1 || 0} ${translations[currentLang].referrals || 'referrals'}`;
        document.getElementById('level-2-count').innerText = `${data.level_2 || 0} ${translations[currentLang].referrals || 'referrals'}`;
        document.getElementById('level-3-count').innerText = `${data.level_3 || 0} ${translations[currentLang].referrals || 'referrals'}`;
    } catch (e) {
        console.error('[ERROR] Failed to fetch referral stats:', e);
        document.getElementById('referral-link').innerText = 'Error loading stats';
    }
}

// Copy referral link to clipboard
function copyReferralLink() {
    const link = document.getElementById('referral-link').innerText;

    if (link && link !== 'https://t.me/bot?start=...') {
        navigator.clipboard.writeText(link).then(() => {
            // Show toast notification
            const toast = document.getElementById('toast-notification');
            if (toast) {
                toast.innerText = 'Referral link copied!';
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2000);
            }

            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        }).catch(err => {
            console.error('[ERROR] Failed to copy:', err);
        });
    }
}

// Setup referral button listener
function setupReferralButton() {
    const referralBtn = document.getElementById('btn-referral');
    if (referralBtn) {
        referralBtn.onclick = openReferralModal;
    }
}
// === COIN MANAGEMENT FUNCTIONS ===

let currentManageExchange = { userId: null, exchangeName: null };

// Open coin management modal
async function openCoinManagement(userId, exchangeName) {
    try {
        currentManageExchange = { userId, exchangeName };

        // Set exchange info
        // Set exchange info
        const displayExchangeName = exchangeName.toLowerCase() === 'okx' ? 'OKX' : exchangeName.toUpperCase();
        if (exchangeName.toLowerCase() === 'okx') {
            document.getElementById('mc-exchange-icon').querySelector('img').src = `logo_bots/okx.png`;
        } else {
            document.getElementById('mc-exchange-icon').querySelector('img').src = `exchange_${exchangeName}.svg`;
        }
        document.getElementById('mc-exchange-name').textContent = displayExchangeName;

        // Fetch existing coins
        const response = await fetch(`${API_BASE}/api/get_coin_configs?user_id=${userId}&exchange=${exchangeName}`);
        const data = await response.json();
        const coins = data.coins || [];

        // Render existing coins
        renderExistingCoins(coins);

        // Show modal
        document.getElementById('modal-manage-coins').style.display = 'flex';

        // Hide add coin selector initially
        document.getElementById('add-coin-selector').style.display = 'none';

        // Apply translations
        applyTranslations();

        if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
    } catch (error) {
        console.error('Error opening coin management:', error);
    }
}

// Close coin management modal
function closeManageCoins() {
    document.getElementById('modal-manage-coins').style.display = 'none';
    // Refresh My Exchanges page
    loadMyExchanges();
}

// Render existing coin configurations
function renderExistingCoins(coins) {
    const container = document.getElementById('existing-coins-list');
    container.innerHTML = '';

    const coinDetails = {
        'BTC/USDT': { name: 'Bitcoin', img: 'bitcoin.png' },
        'ETH/USDT': { name: 'Ethereum', img: 'ethereum.png' },
        'BNB/USDT': { name: 'BNB', img: 'bnb.png' },
        'OKB/USDT': { name: 'OKB', img: 'okb.png' }
    };

    const externalBtn = document.querySelector('#modal-manage-coins .btn-add-coin');

    const t = translations[currentLang] || translations['en'];

    if (coins.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px 20px; color: #9CA3AF; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 200px;">
                <div style="font-size: 14px; margin-bottom: 4px;">${t.no_coins_yet || 'No coins configured yet'}</div>
                <div style="font-size: 12px; margin-bottom: 24px;">${t.no_coins_hint || 'Click below to add a coin'}</div>
                <button id="inline-add-coin-btn" style="width: 100%; padding: 14px; background: #467EE7; color: white; border: none; border-radius: 12px; font-weight: 600; font-size: 14px; cursor: pointer; box-shadow: 0 4px 12px rgba(70, 126, 231, 0.3);">${t.btn_add_new_coin || '+ Add New Coin'}</button>
            </div>
        `;
        // Attach event listener after injection
        const inlineBtn = document.getElementById('inline-add-coin-btn');
        if (inlineBtn) {
            inlineBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                window.showAddCoinSelector();
            });
        }
        if (externalBtn) externalBtn.style.display = 'none';
        return;
    }

    if (externalBtn) externalBtn.style.display = 'block';

    coins.forEach(coin => {
        const details = coinDetails[coin.symbol] || { name: coin.symbol, img: 'bitcoin.png' };
        const html = `
            <div class="coin-item" data-symbol="${coin.symbol}">
                <div class="coin-item-left">
                    <img src="coin_img/${details.img}" class="coin-item-icon">
                    <div class="coin-item-info">
                        <div class="coin-item-symbol">${details.name}</div>
                        <div class="coin-item-details">
                            <span data-i18n="capital">Capital</span>: $${coin.reserved_amount} | 
                            <span data-i18n="risk">Risk</span>: ${coin.risk_pct}%
                        </div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="icon-btn" onclick="editCoinConfig('${currentManageExchange.exchangeName}', '${coin.symbol}', ${coin.reserved_amount}, ${coin.risk_pct})" title="Edit"><img src="edit.svg" width="16" height="16"></button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });

    applyTranslations();
}

// Show coin selector for adding new coins
window.showAddCoinSelector = async function () {
    console.log('[coin] START: showAddCoinSelector triggered');

    try {
        console.log('[coin] Current Exchange:', currentManageExchange);

        // Get existing coins
        const url = `${API_BASE}/api/get_coin_configs?user_id=${currentManageExchange.userId}&exchange=${currentManageExchange.exchangeName}`;
        console.log('[coin] Fetching URL:', url);

        const response = await fetch(url);
        const data = await response.json();
        const existingCoins = (data.coins || []).map(c => c.symbol);
        console.log('[coin] Existing Coins:', existingCoins);

        // Available coins
        const allCoins = [
            { symbol: 'BTC/USDT', name: 'Bitcoin', img: 'bitcoin.png' },
            { symbol: 'ETH/USDT', name: 'Ethereum', img: 'ethereum.png' },
            { symbol: 'BNB/USDT', name: 'BNB', img: 'bnb.png' },
            { symbol: 'OKB/USDT', name: 'OKB', img: 'okb.png' }
        ];

        // Filter out already added coins (Case insensitive check)
        const availableCoins = allCoins.filter(c =>
            !existingCoins.some(existing => existing.toUpperCase() === c.symbol.toUpperCase())
        );
        console.log('[coin] Available Coins to render:', availableCoins);

        const grid = document.getElementById('available-coins-grid');
        console.log('[coin] Grid Element:', grid);

        if (grid) {
            grid.innerHTML = '';
            const t = translations[currentLang] || translations['en'];
            if (availableCoins.length === 0) {
                grid.innerHTML = `<div style="color: #9CA3AF; text-align: center; padding: 20px;">${t.all_coins_added || 'All coins already added'}</div>`;
            } else {
                availableCoins.forEach(coin => {
                    const html = `
                        <div class="coin-card" onclick="addNewCoin('${coin.symbol}')" style="display:flex; flex-direction:column; align-items:center; padding:12px; background:#1A1926; border-radius:12px; border:1px solid rgba(255,255,255,0.1); cursor:pointer;">
                            <img src="coin_img/${coin.img}" width="40" height="40" style="margin-bottom: 8px;">
                            <div style="font-size: 14px; font-weight: 600; color: #fff;">${coin.name}</div>
                            <div style="font-size: 12px; color: #9CA3AF;">${coin.symbol}</div>
                        </div>
                    `;
                    grid.insertAdjacentHTML('beforeend', html);
                });
            }
        } else {
            console.error('[coin] Grid element not found!');
        }

        // Show selector container
        const selector = document.getElementById('add-coin-selector');
        if (selector) {
            selector.style.display = 'block';
            console.log('[coin] Selector made visible');

            // Scroll logic - Target the grid itself
            setTimeout(() => {
                const grid = document.getElementById('available-coins-grid');
                if (grid && grid.lastElementChild) {
                    grid.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    console.log('[coin] Scrolled to last coin');
                } else if (selector) {
                    selector.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    console.log('[coin] Scrolled to selector start');
                }
            }, 150);
        } else {
            console.error('[coin] Selector container not found!');
        }

    } catch (error) {
        console.error('[coin] Error in showAddCoinSelector:', error);
        alert('Error: ' + error.message);
    }
}

// Add new coin with configuration modal
let addingCoinSymbol = null;

function addNewCoin(symbol) {
    const modal = document.getElementById('modal-add-coin');
    if (!modal) return;

    addingCoinSymbol = symbol;

    // Set Values
    document.getElementById('ac-symbol').innerText = symbol;
    document.getElementById('ac-exchange').innerText = currentManageExchange.exchangeName.toUpperCase();
    document.getElementById('ac-capital').value = '';
    document.getElementById('ac-risk').value = '1.0'; // Default risk

    // Set Icon
    const iconMap = {
        'BTC/USDT': 'bitcoin.png',
        'ETH/USDT': 'ethereum.png',
        'BNB/USDT': 'bnb.png',
        'OKB/USDT': 'okb.png'
    };
    const imgName = iconMap[symbol] || 'usdt_bep_icon.svg';
    const src = imgName.includes('svg') ? imgName : `coin_img/${imgName}`;
    document.querySelector('#ac-icon img').src = src;

    modal.style.display = 'flex';
    applyTranslations();
}

function closeAddCoinModal() {
    document.getElementById('modal-add-coin').style.display = 'none';
    addingCoinSymbol = null;
}


async function submitAddCoin() {
    if (!addingCoinSymbol) return;

    const capital = parseFloat(document.getElementById('ac-capital').value);
    const risk = parseFloat(document.getElementById('ac-risk').value);

    // Validation
    if (isNaN(capital) || capital < 0) {
        alert('Invalid capital amount');
        return;
    }

    if (isNaN(risk) || risk < 0.1 || risk > 10) {
        alert('Risk must be between 0.1% and 10%');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/save_coin_configs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentManageExchange.userId,
                exchange: currentManageExchange.exchangeName,
                coins: [{
                    symbol: addingCoinSymbol,
                    capital: capital,
                    risk: risk
                }]
            })
        });

        const data = await response.json();

        // Handle both "ok" status and "success" boolean which might vary by endpoint
        if (data.status === 'ok' || data.success === true) {
            showToast(getTranslation('toast_coin_added') || 'Coin added');
            closeAddCoinModal();
            // Refresh coin list in the manage modal
            openCoinManagement(currentManageExchange.userId, currentManageExchange.exchangeName);
            // Also refresh main user data slightly later
            setTimeout(async () => {
                await fetchUserData(currentManageExchange.userId);
            }, 800);
        } else {
            let msg = data.detail || data.message || 'Failed to add coin';
            if (typeof msg === 'object') msg = JSON.stringify(msg);
            alert(msg);
        }
    } catch (error) {
        console.error('Error adding coin:', error);
        alert('Network error');
    }
}



// Remove coin


function getTranslation(key) {
    return translations[currentLang][key] || key;
}

// === MISSING UTILITY FUNCTIONS ===

function applyTranslations() {
    const t = translations[currentLang];
    if (!t) return;
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.innerHTML = t[key];
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (t[key]) el.placeholder = t[key];
    });
}

function loadMyExchanges() {
    // Refresh main user data which re-renders exchanges
    const user = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) ? tg.initDataUnsafe.user : null;
    if (user && user.id) {
        fetchUserData(user.id);
    }
}
