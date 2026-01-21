// --- INITIAL VARIABLES ---
const API_BASE = "";
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
        btn_apply_changes: "Apply Changes"
    },
    ru: {
        welcome: "С возвращением",
        lbl_total_balance: "Стоимость портфеля",
        btn_topup: "Пополнить баланс",
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
        top_up_title: "Пополнить баланс",
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
        msg_edit_risk_prompt: "Процент капитала, рискуемый на каждую сделку.",
        btn_disconnect: "Отключить стратегию",
        btn_apply_changes: "Применить изменения"
    },
    uk: {
        welcome: "З поверненням",
        lbl_total_balance: "Портфель",
        btn_topup: "Поповнити",
        btn_copy_trade: "Копітрейдинг",
        active_strategies: "Активні Стратегії",
        view_all: "Всі",
        my_exchanges: "Мої Біржі",
        settings: "Налаштування",
        language: "Мова",
        user_id: "ID користувача",
        lbl_alladeen_fees: "Баланс USDT",
        wiz_title: "Налаштування копітрейдингу",
        btn_connect: "Підключити",
        success: "Успіх!",
        reserve_title: "Торговий Капітал",
        save: "Зберегти",
        top_up_title: "Поповнити баланс",
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
        btn_apply_changes: "Застосувати зміни"
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

        renderExchanges(data.exchanges);
        renderActiveStrategies(data.exchanges);
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
function renderExchanges(exchanges) {
    const list = document.getElementById("exchange-list");
    if (!list) return;
    list.innerHTML = "";

    // Filter: Show ONLY connected + Error (to debug)
    const active = exchanges ? exchanges.filter(ex => ex.status === "Connected" || ex.status === "Error") : [];

    if (active.length === 0) {
        list.innerHTML = `<div class="fade-in" style="padding:20px; text-align:center; color:#555;">No connected exchanges</div>`;
        return;
    }

    const creditsEl = document.getElementById("credits-bal");
    const creditsStr = creditsEl ? creditsEl.innerText : "0";
    const credits = parseFloat(creditsStr) || 0;
    const t = translations[currentLang] || translations['en'];

    active.forEach((ex, idx) => {
        const isConnected = ex.status === "Connected";
        const stratName = ex.strategy === 'cgt' ? 'TradeMax' : 'Bing-Bot';
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

        // Pass balance and statusText to openStrategySettings
        // Note: We escape string arguments with single quotes
        const isConnectedStr = isConnected ? 'true' : 'false';
        const html = `
            <div class="strategy-item fade-in" onclick="console.log('Clicked ${ex.name}'); openStrategySettings('${ex.name}', ${ex.reserve || 0}, ${ex.risk || 1}, ${isConnectedStr}, ${balance}, '${statusText}');" style="animation-delay: ${idx * 0.1}s; justify-content: space-between; cursor: pointer;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div class="strat-icon">
                        <img src="${logoPath}">
                    </div>
                    <div class="strat-info">
                        <div class="strat-title">${stratName}</div>
                        <div class="strat-desc" style="color: #aaa;">${statusText}</div>
                    </div>
                </div>
                <div style="text-align:right;">
                     <div class="strat-title" style="font-size:16px;">$${balance.toFixed(2)}</div>
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

    const creditsEl = document.getElementById("credits-bal");
    const creditsStr = creditsEl ? creditsEl.innerText : (document.getElementById("credits-bal-settings")?.innerText || "0");
    const credits = parseFloat(creditsStr) || 0;
    const t = translations[currentLang] || translations['en'];

    // Filter for connected exchanges (include Error status to prevent disappearance)
    const active = exchanges ? exchanges.filter(ex => ex.status === "Connected" || ex.status === "Error") : [];

    if (active.length === 0) {
        container.innerHTML = `<div class="fade-in" style="text-align:center; padding:20px; color:#888; font-size:14px;">${t.no_active_strategies || "No active strategies"}</div>`;
        return;
    }

    active.forEach((ex, idx) => {
        const stratName = ex.strategy === 'cgt' ? 'TradeMax' : 'Bing-Bot';
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
            await fetch(`${API_BASE} /api/topup`, {
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
    console.log('[DEBUG] setupActionButtons called');

    // Top Up Card
    const topUpCard = document.querySelector('.action-card[data-action="topup"]');
    console.log('[DEBUG] topUpCard found:', topUpCard);

    if (topUpCard) {
        topUpCard.addEventListener('click', () => {
            console.log('[DEBUG] Top Up clicked!');
            const modal = document.getElementById('modal-topup');
            console.log('[DEBUG] Modal element:', modal);

            if (modal) {
                modal.classList.add('sheet-mode');
                modal.style.display = 'flex';
                fetchDepositAddress();
            } else {
                console.error('[ERROR] modal-topup not found!');
            }
        });
        console.log('[DEBUG] Top Up click listener attached');
    } else {
        console.error('[ERROR] Top Up card not found!');
    }

    const ctCard = document.getElementById('btn-copy-trading');
    if (ctCard) {
        ctCard.addEventListener('click', () => {
            try {
                console.log('[DEBUG] Copy Trade Btn Clicked (ID)');
                const modal = document.getElementById('modal-copytrading');
                if (!modal) throw new Error("Modal not found");

                modal.style.display = 'flex';
                if (typeof showCTStep === 'function') showCTStep('strategy');

                if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            } catch (e) {
                alert("CT ERROR: " + e.message);
            }
        });
    } else {
        console.error('[ERROR] Copy Trade ID not found');
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
            showToast("Changes Applied ✅");
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
                    showToast("Strategy Disconnected 🔌");
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

        const res = await fetch('/api/create_payment', {
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
    } catch (e) {
        console.error(e);
        addrEl.innerText = "Connection Failed";
    }
}

// === COPY TRADING MODAL ===
function setupCopyTradingModal() {
    const modal = document.getElementById('modal-copytrading');
    if (!modal) {
        console.error("[ERROR] Modal #modal-copytrading NOT found in DOM.");
        return;
    }
    console.log("[DEBUG] setupCopyTradingModal: Modal found. Attaching delegated click listener.");

    // Event Delegation: Listen on the modal for clicks on .strategy-selector-btn
    modal.addEventListener('click', (e) => {
        // Look for the closest strategy button (in case user clicks on image or text inside)
        const btn = e.target.closest('.strategy-selector-btn');
        if (btn) {
            const strategy = btn.dataset.strategy;
            const exchange = btn.dataset.exchange;
            console.log(`[DEBUG] CLICK detected on Strategy Button. Strategy: ${strategy}, Exchange: ${exchange}`);

            if (exchange === 'bingx') showCTStep('bingx-api');
            else if (exchange === 'okx') showCTStep('okx-api');
            else console.warn(`[WARN] Unknown exchange: ${exchange}`);

            if (window.tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        }
    });
}

function showCTStep(stepName) {
    console.log(`[DEBUG] showCTStep called with: ${stepName}`);

    const steps = document.querySelectorAll('.ct-step');
    steps.forEach(step => step.style.display = 'none');

    const targetId = `ct-step-${stepName}`;
    const targetStep = document.getElementById(targetId);

    // Dynamic Height Adjustment
    const modalContent = document.querySelector('#modal-copytrading .modal-content');
    if (modalContent) {
        if (stepName === 'bingx-api' || stepName === 'okx-api') {
            // Expand for API forms
            modalContent.style.height = '85vh'; // Use viewport percentage
            modalContent.style.overflowY = 'auto'; // Enable scrolling
            modalContent.style.transition = 'height 0.3s ease'; // Smooth transition
        } else {
            // Reset for strategy selection (or other small steps)
            modalContent.style.height = '580px';
            modalContent.style.overflowY = 'hidden';
        }
    }

    if (targetStep) {
        targetStep.style.display = 'block';
        console.log(`[DEBUG] SUCCESS: Switched to step #${targetId}`);
    } else {
        console.error(`[ERROR] FAILED to find step with ID #${targetId}`);
        // Debug: list available IDs
        console.log("Available steps:", Array.from(steps).map(s => s.id));
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
        // Always reset to strategy step
        showCTStep('strategy');
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

    if (!apiKey || !secretKey || !capital || capital <= 0) {
        alert('Please fill all fields correctly');
        return;
    }

    try {
        const user = tg.initDataUnsafe.user;
        const response = await fetch(`${API_BASE}/api/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange_name: 'bingx',
                strategy: 'bingbot',
                api_key: apiKey,
                secret_key: secretKey,
                password: '',
                reserve_amount: capital
            })
        });

        const data = await response.json();
        if (data.success) {
            showToast('BingX Connected!');
            closeCopyTradingModal();
            await fetchUserData(user.id);
        } else {
            alert(data.message || 'Connection failed');
        }
    } catch (error) {
        console.error(error);
        alert('Connection error');
    }
}

async function submitOKXAPI() {
    const apiKey = document.getElementById('okx-api-key').value.trim();
    const secretKey = document.getElementById('okx-secret-key').value.trim();
    const passphrase = document.getElementById('okx-passphrase').value.trim();
    const capital = parseFloat(document.getElementById('okx-capital').value);

    if (!apiKey || !secretKey || !passphrase || !capital || capital <= 0) {
        alert('Please fill all fields correctly');
        return;
    }

    try {
        const user = tg.initDataUnsafe.user;
        const response = await fetch(`${API_BASE}/api/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: user.id,
                exchange_name: 'okx',
                strategy: 'trademax',
                api_key: apiKey,
                secret_key: secretKey,
                password: passphrase,
                reserve_amount: capital
            })
        });

        const data = await response.json();
        if (data.success) {
            showToast('OKX Connected!');
            closeCopyTradingModal();
            await fetchUserData(user.id);
        } else {
            alert(data.message || 'Connection failed');
        }
    } catch (error) {
        console.error(error);
        alert('Connection error');
    }
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
    showToast("Address Copied!");
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

