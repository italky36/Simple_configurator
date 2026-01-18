(function ($) {
  const BACKEND_BASE = "https://93-170-123-229.nip.io";
  const API_BASE = BACKEND_BASE + "/api";
  const LEAD_ENDPOINT = API_BASE + "/lead";
  // Базовый префикс для статики (шрифты/изображения). Для Tilda ставим явный домен.
  const DEFAULT_ASSETS_BASE = "https://coffeezonefranchise.ru";
  const ASSETS_BASE =
    (typeof window !== "undefined" && window.CZ_ASSETS_BASE) ||
    DEFAULT_ASSETS_BASE;

  const state = { machines: [], specs: {}, current: null };
  const skipValues = new Set(["нет", "не", "-", "none", "", null, undefined]);
  const STORAGE_KEY = "cz-conf-selection";
  const UE_STORAGE_KEY = "cz-ue-selection";
  const DATA_CACHE_KEY = "cz-conf-cache-v1";
  const CACHE_TTL_MS = 12 * 60 * 60 * 1000;
  const UE_DEFAULTS = { price: 100, monthly: 500 };
  const UE_MODES = { OWN: "own", RENT: "rent" };
  const UE_SHARES = {
    own: {
      partner: 0.55,
      company: 0.45,
      note: "За ингредиенты, их доставку и сопровождение",
    },
    rent: {
      partner: 0.25,
      company: 0.75,
      note: "За оборудование, ингредиенты, их доставку и сопровождение",
    },
  };
  const UE_PIE_RADIUS = 48;
  const UE_PIE_CIRC = 2 * Math.PI * UE_PIE_RADIUS;

  // Флаг: была ли уже показана анимация shrug за сессию
  let ozonShrugAnimationShown = false;

  // Цвета: английские ключи для данных
  const FRAME_COLORS = ["white", "black"];
  const INSERT_COLORS = ["yellow", "green", "red", "gray", "blue", "purple"];

  // Цвета дизайна, которые временно скрываем из селектора (ключи нормализуются)
  const HIDDEN_DESIGN_COLORS = {
    orange: true,
    оранжевый: true,
    фиолетовый: true,
  };

  // Маппинг английских ключей на русские названия
  const COLOR_LABELS = {
    white: "Белый",
    black: "Чёрный",
    yellow: "Жёлтый",
    green: "Зелёный",
    red: "Красный",
    gray: "Серый",
    blue: "Синий",
    purple: "Фиолетовый",
  };

  // Кеш предзагруженных изображений
  const imageCache = new Map();

  const normalizeColorKey = (key) => {
    if (!key) return "";
    const k = String(key).trim().toLowerCase();
    const map = {
      white: "white",
      белый: "white",
      белая: "white",
      бел: "white",
      black: "black",
      чёрный: "black",
      черный: "black",
      черная: "black",
      yellow: "yellow",
      желтый: "yellow",
      желтая: "yellow",
      green: "green",
      зеленый: "green",
      зеленая: "green",
      red: "red",
      красный: "red",
      красная: "red",
      gray: "gray",
      серый: "gray",
      серая: "gray",
      grey: "gray",
      blue: "blue",
      синий: "blue",
      синяя: "blue",
      orange: "orange", // ✅ ДОБАВЛЕНО
      оранжевый: "orange", // ✅ ДОБАВЛЕНО
      оранжевая: "orange", // ✅ ДОБАВЛЕНО
      purple: "purple",
      фиолетовый: "purple",
      фиолетовая: "purple",
    };
    return map[k] || k;
  };

  const isHiddenDesignColor = (key) =>
    !!HIDDEN_DESIGN_COLORS[normalizeColorKey(key)];

  // Предзагрузка изображения в кеш
  function preloadImage(src) {
    if (!src || imageCache.has(src)) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        imageCache.set(src, img);
        resolve(img);
      };
      img.onerror = reject;
      img.src = src;
    });
  }

  // Предзагрузка всех изображений для варианта
  function preloadVariantImages(v) {
    if (!v) return;
    const imagesToPreload = [];

    if (v.main_image) {
      imagesToPreload.push(normSrc(v.main_image));
    }

    if (v.design_images) {
      Object.values(v.design_images).forEach((frameColors) => {
        Object.values(frameColors).forEach((config) => {
          if (config.main_image || config.main_image_path) {
            imagesToPreload.push(
              normSrc(config.main_image || config.main_image_path)
            );
          }
        });
      });
    }

    imagesToPreload.forEach((src) => preloadImage(src));
  }

  // Утилиты
  const $el = (cls) => $(cls).first();
  const setText = (jq, txt) => jq.length && jq.text(txt || "—");
  const fmtPrice = (v) =>
    v || v === 0 ? Number(v).toLocaleString("ru-RU") + " ₽" : "—";

  const parseNumber = (value) => {
    if (value === null || value === undefined) return Number.NaN;
    const normalized = String(value).replace(",", ".").trim();
    if (!normalized) return Number.NaN;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  };

  const normalizeUeValue = (value, min, max, fallback) => {
    const parsed = parseNumber(value);
    if (!Number.isFinite(parsed)) return fallback;
    let next = parsed;
    if (Number.isFinite(min)) next = Math.max(min, next);
    if (Number.isFinite(max)) next = Math.min(max, next);
    return next;
  };

  const formatRub = (value) => {
    if (!Number.isFinite(value)) return "—";
    return Math.round(value).toLocaleString("ru-RU") + " ₽";
  };

  const formatCount = (value) => {
    if (!Number.isFinite(value)) return "—";
    const rounded = Math.round(value * 10) / 10;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  };

  const UE_COUNTUP_MS = 500;
  const prefersReducedMotion = false;

  const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

  const formatMonths = (value) => {
    if (!Number.isFinite(value)) return "—";
    const rounded = Math.round(value * 10) / 10;
    return `${rounded.toLocaleString("ru-RU")} мес.`;
  };

  const animateNumber = ($el, target, formatter, options = {}) => {
    if (!$el.length) return;
    if (!Number.isFinite(target)) {
      $el.text("—");
      $el.removeData("num");
      return;
    }

    const animate = options.animate !== false;
    const duration = options.duration || UE_COUNTUP_MS;
    const previous = $el.data("num");
    const start = Number.isFinite(previous) ? previous : 0;

    if (!animate || prefersReducedMotion || start === target) {
      $el.text(formatter(target));
      $el.data("num", target);
      return;
    }

    const prevFrame = $el.data("animFrame");
    if (prevFrame) {
      cancelAnimationFrame(prevFrame);
    }

    const from = start;
    const to = target;
    const startTime = performance.now();

    const step = (now) => {
      const t = Math.min(1, (now - startTime) / duration);
      const eased = easeOutCubic(t);
      const current = from + (to - from) * eased;
      $el.text(formatter(current));
      if (t < 1) {
        const frameId = requestAnimationFrame(step);
        $el.data("animFrame", frameId);
      } else {
        $el.text(formatter(to));
        $el.data("num", to);
        $el.removeData("animFrame");
      }
    };

    const frameId = requestAnimationFrame(step);
    $el.data("animFrame", frameId);
  };

  const clamp01 = (value) => Math.max(0, Math.min(1, value));

  // Сброс сохраненных значений для анимации
  const resetAnimationData = () => {
    const $calc = $(".ue-calc");
    if (!$calc.length) return;
    $calc.find("[data-ue]").each(function() {
      $(this).removeData("num").removeData("animFrame");
    });
  };

  // ❌ ОТКЛЮЧЕНО: Динамическое изменение цвета диаграммы
  // const getProfitColor = (ratio) => {
  //   const startHue = 210;
  //   const endHue = 125;
  //   const t = clamp01(ratio);
  //   const hue = startHue + (endHue - startHue) * t;
  //   return `hsl(${hue}, 75%, 42%)`;
  // };

  const normSrc = (src) => {
    if (!src) return "";
    if (/^(https?:)?\/\//i.test(src) || src.startsWith("data:")) return src;
    const base = BACKEND_BASE.replace(/\/+$/, "");
    const path = src.startsWith("/") ? src : "/" + src;
    return base + path;
  };

  // Построение URL для статики (шрифты, изображения) с учётом кастомного домена
  const assetUrl = (path) => {
    if (!path) return "";
    if (/^(https?:)?\/\//i.test(path) || path.startsWith("data:")) return path;
    const rawBase =
      (typeof window !== "undefined" && window.CZ_ASSETS_BASE) ||
      ASSETS_BASE ||
      DEFAULT_ASSETS_BASE;
    const cleanBase = (
      rawBase && rawBase.trim() ? rawBase : DEFAULT_ASSETS_BASE
    ).replace(/\/+$/, "");
    const cleanPath = path.replace(/^\/+/, "");
    return `${cleanBase}/${cleanPath}`;
  };

  const normVal = (v) =>
    v === null || v === undefined ? "" : String(v).trim().toLowerCase();
  const showInitialLoader = () =>
    $(".cfg-initial-loader").removeClass("is-hidden");
  const hideInitialLoader = () =>
    $(".cfg-initial-loader").addClass("is-hidden");

  function applyLoadedData(res) {
    state.machines = res?.machines || [];
    state.specs = {};
    (res?.specs || []).forEach((sp) => {
      if (!state.specs[sp.category]) state.specs[sp.category] = {};
      state.specs[sp.category][sp.name] = sp;
    });
    console.log("📦 Loaded machines:", state.machines.length);
    state.machines.forEach((m) => {
      if (m.design_images) {
        console.log(
          `  Machine ${m.id} (${m.name}) has design_images:`,
          Object.keys(m.design_images)
        );
      }
    });

    // ✅ ДОБАВЛЕНО: Отладка цветов дизайна
    const uniqueDesignColors = new Set();
    state.machines.forEach((m) => {
      if (m.frame_design_color && m.ozon_link) {
        uniqueDesignColors.add(m.frame_design_color);
      }
    });

    console.log(
      "🎨 Уникальные цвета дизайна с Ozon ссылками:",
      Array.from(uniqueDesignColors)
    );

    console.log(
      "🔄 После нормализации:",
      Array.from(uniqueDesignColors).map((c) => ({
        original: c,
        normalized: normalizeColorKey(c),
      }))
    );
  }

  function loadCachedData() {
    try {
      const raw = localStorage.getItem(DATA_CACHE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.timestamp || !parsed.data) return null;
      if (Date.now() - parsed.timestamp > CACHE_TTL_MS) return null;
      return parsed.data;
    } catch (e) {
      return null;
    }
  }

  function saveCachedData(data) {
    try {
      localStorage.setItem(
        DATA_CACHE_KEY,
        JSON.stringify({ timestamp: Date.now(), data })
      );
    } catch (e) {}
  }

  const excludedVariants = new Set();

  function findFirstDesignImageConfig(designImages) {
    if (!designImages) return null;
    for (const [frameColorKey, inserts] of Object.entries(designImages)) {
      const normFrame = normalizeColorKey(frameColorKey);
      if (
        !inserts ||
        typeof inserts !== "object" ||
        !Object.keys(inserts).length
      )
        continue;
      for (const [insertColorKey, cfg] of Object.entries(inserts)) {
        const normInsert = normalizeColorKey(insertColorKey);
        if (cfg && (cfg.main_image || cfg.main_image_path)) {
          return {
            frameColor: normFrame || frameColorKey,
            insertColor: normInsert || insertColorKey,
            config: cfg,
          };
        }
      }
    }
    return null;
  }

  function findDesignImageForFrame(designImages, frameColorKey) {
    if (!designImages || !frameColorKey) return null;
    const normFrame = normalizeColorKey(frameColorKey);
    const inserts = Object.entries(designImages).find(
      ([key]) => normalizeColorKey(key) === normFrame
    )?.[1];
    if (!inserts || typeof inserts !== "object" || !Object.keys(inserts).length)
      return null;
    for (const [insertColorKey, cfg] of Object.entries(inserts)) {
      const normInsert = normalizeColorKey(insertColorKey);
      if (cfg && (cfg.main_image || cfg.main_image_path)) {
        return {
          frameColor: normFrame || frameColorKey,
          insertColor: normInsert || insertColorKey,
          config: cfg,
        };
      }
    }
    return null;
  }

  function getDesignConfig(v, frameColor, insertColor) {
    if (!v.design_images) return null;
    const normFrame = normalizeColorKey(frameColor);
    const normInsert = normalizeColorKey(insertColor);

    const tryFrames = [frameColor, normFrame].filter(Boolean);
    const tryInserts = [insertColor, normInsert].filter(Boolean);

    for (const fKey of tryFrames) {
      const frameEntry = Object.entries(v.design_images).find(
        ([key]) => normalizeColorKey(key) === normalizeColorKey(fKey)
      );
      if (!frameEntry) continue;
      const inserts = frameEntry[1];
      for (const iKey of tryInserts) {
        const insertEntry = Object.entries(inserts).find(
          ([key]) => normalizeColorKey(key) === normalizeColorKey(iKey)
        );
        if (insertEntry) {
          const cfg = insertEntry[1];
          if (cfg && (cfg.main_image || cfg.main_image_path)) {
            return {
              frameColor: normalizeColorKey(frameEntry[0]) || frameEntry[0],
              insertColor: normalizeColorKey(insertEntry[0]) || insertEntry[0],
              config: cfg,
            };
          }
        }
      }
    }
    return null;
  }

  function saveSelection() {
    const data = {
      machine: $el(".cfg-select-machine").val() || "",
      frame: $el(".cfg-select-frame").val() || "",
      frame_color: $el(".cfg-select-frame-color").val() || "",
      insert_color: $el(".cfg-select-insert-color").val() || "",
      fridge: $el(".cfg-select-fridge").val() || "",
      terminal: $el(".cfg-select-terminal").val() || "",
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  function loadSelection() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function loadUnitEconomicsSelection() {
    try {
      const raw = localStorage.getItem(UE_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function getUnitEconomicsSelection() {
    const $calc = $(".ue-calc");
    if (!$calc.length) return null;
    const $priceRange = $calc.find("[data-ue='price-range']");
    const $priceInput = $calc.find("[data-ue='price-input']");
    const $monthlyRange = $calc.find("[data-ue='monthly-range']");
    const $monthlyInput = $calc.find("[data-ue='monthly-input']");
    if (
      !$priceRange.length ||
      !$priceInput.length ||
      !$monthlyRange.length ||
      !$monthlyInput.length
    )
      return null;

    const price = normalizeUeValue(
      $priceInput.val(),
      parseNumber($priceRange.attr("min")),
      parseNumber($priceRange.attr("max")),
      UE_DEFAULTS.price,
    );
    const monthly = normalizeUeValue(
      $monthlyInput.val(),
      parseNumber($monthlyRange.attr("min")),
      parseNumber($monthlyRange.attr("max")),
      UE_DEFAULTS.monthly,
    );
    const mode =
      $calc.attr("data-ue-mode") === UE_MODES.RENT ? UE_MODES.RENT : UE_MODES.OWN;

    return { mode, price, monthly };
  }

  function saveUnitEconomicsSelection(selection) {
    const data = selection || getUnitEconomicsSelection();
    if (!data) return;
    try {
      localStorage.setItem(UE_STORAGE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  function setUeRangeFill($range) {
    if (!$range.length) return;
    const min = parseNumber($range.attr("min"));
    const max = parseNumber($range.attr("max"));
    const value = parseNumber($range.val());
    if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return;
    const percent = ((value - min) / (max - min)) * 100;
    const clamped = Math.min(100, Math.max(0, percent));
    $range[0].style.setProperty("--ue-range-value", `${clamped}%`);
  }

  function readUeControl($range, $input, fallback, options = {}) {
    if (!$range.length || !$input.length) return fallback;
    const sync = options.sync !== false;
    const min = parseNumber($range.attr("min"));
    const max = parseNumber($range.attr("max"));
    const rawValue = options.rawValue !== undefined ? options.rawValue : $input.val();
    const value = normalizeUeValue(rawValue, min, max, fallback);
    if (sync) {
      $range.val(value);
      $input.val(value);
    }
    setUeRangeFill($range);
    return value;
  }

  const ueWarningTimers = { price: null, monthly: null };
  const UE_WARNING_TIMEOUT_MS = 2500;

  function setUeWarning($warning, key, message) {
    if (!$warning.length) return;
    if (message) {
      $warning.addClass("is-visible");
      $warning.find("span").text(message);
      if (ueWarningTimers[key]) {
        clearTimeout(ueWarningTimers[key]);
      }
      ueWarningTimers[key] = setTimeout(() => {
        $warning.removeClass("is-visible");
        ueWarningTimers[key] = null;
      }, UE_WARNING_TIMEOUT_MS);
    } else {
      $warning.removeClass("is-visible");
      if (ueWarningTimers[key]) {
        clearTimeout(ueWarningTimers[key]);
        ueWarningTimers[key] = null;
      }
    }
  }

  function setUnitEconomicsMode(mode, skipUpdate = false, skipSave = false) {
    const $calc = $(".ue-calc");
    if (!$calc.length) return;
    const normalized = mode === UE_MODES.RENT ? UE_MODES.RENT : UE_MODES.OWN;
    $calc.attr("data-ue-mode", normalized);
    $calc.find(".ue-toggle-btn").removeClass("is-active");
    $calc.find(`.ue-toggle-btn[data-ue-mode='${normalized}']`).addClass("is-active");
    if (!skipUpdate) {
      updateUnitEconomics(state.current, { animate: true, duration: 500 });
    }
    if (!skipSave) {
      saveUnitEconomicsSelection();
    }
  }

  function updateUnitEconomics(variant, options = {}) {
    const $calc = $(".ue-calc");
    if (!$calc.length) return;
    const syncInputs = options.syncInputs !== false;
    const animateNumbers = options.animate !== false;
    const animDuration = options.duration || UE_COUNTUP_MS;

    const price = readUeControl(
      $calc.find("[data-ue='price-range']"),
      $calc.find("[data-ue='price-input']"),
      UE_DEFAULTS.price,
      { sync: syncInputs, rawValue: options.priceOverride }
    );
    const monthly = readUeControl(
      $calc.find("[data-ue='monthly-range']"),
      $calc.find("[data-ue='monthly-input']"),
      UE_DEFAULTS.monthly,
      { sync: syncInputs, rawValue: options.monthlyOverride }
    );

    const mode = $calc.attr("data-ue-mode") === UE_MODES.RENT ? UE_MODES.RENT : UE_MODES.OWN;
    const share = UE_SHARES[mode];
    const gross = price * monthly;
    const net = gross * 0.97;
    const partnerProfit = net * share.partner;
    const companyShare = net * share.company;
    const perDay = monthly / 30;
    // ❌ ОТКЛЮЧЕНО: Динамическое изменение цвета диаграммы
    // const maxMonthly = parseNumber($calc.find("[data-ue='monthly-range']").attr("max"));
    // const profitRatio =
    //   Number.isFinite(maxMonthly) && maxMonthly > 0 ? monthly / maxMonthly : 0;
    // $calc[0].style.setProperty("--ue-profit-color", getProfitColor(profitRatio));

    animateNumber(
      $calc.find("[data-ue='per-day']"),
      perDay,
      formatCount,
      { animate: animateNumbers, duration: animDuration }
    );
    // ✅ ИЗМЕНЕНО: Показываем цену оборудования вместо выручки
    const equipmentPrice = parseNumber(variant && variant.price);
    animateNumber(
      $calc.find("[data-ue='gross']"),
      equipmentPrice,
      formatRub,
      { animate: animateNumbers, duration: animDuration }
    );
    animateNumber(
      $calc.find("[data-ue='revenue']"),
      gross,
      formatRub,
      { animate: animateNumbers, duration: animDuration }
    );
    animateNumber(
      $calc.find("[data-ue='net']"),
      net,
      formatRub,
      { animate: animateNumbers, duration: animDuration }
    );
    // Проценты (плавно, как остальные значения)
    animateNumber(
      $calc.find("[data-ue='partner-share']"),
      share.partner * 100,
      (value) => `${Math.round(value)}%`,
      { animate: animateNumbers, duration: animDuration }
    );
    animateNumber(
      $calc.find("[data-ue='company-share']"),
      share.company * 100,
      (value) => `${Math.round(value)}%`,
      { animate: animateNumbers, duration: animDuration }
    );

    $calc.find("[data-ue='partner-label']").text(`Партнер`);
    $calc.find("[data-ue='company-label']").text(`Компания`);
    $calc.find("[data-ue='company-note']").text(share.note);
    const partnerPercent = Math.round(share.partner * 100);
    const $piePartner = $calc.find("[data-ue='pie-partner']");
    if ($piePartner.length) {
      const partnerLen = (UE_PIE_CIRC * share.partner).toFixed(2);
      const restLen = (UE_PIE_CIRC - partnerLen).toFixed(2);
      $piePartner.css("stroke-dasharray", `${partnerLen} ${restLen}`);
      $piePartner.css("stroke-dashoffset", "0");
    }
    animateNumber(
      $calc.find("[data-ue='partner-percent']"),
      partnerPercent,
      (value) => `${Math.round(value)}%`,
      { animate: animateNumbers, duration: animDuration }
    );
    animateNumber(
      $calc.find("[data-ue='partner-profit']"),
      partnerProfit,
      formatRub,
      { animate: animateNumbers, duration: animDuration }
    );

    const investment = parseNumber(variant && variant.price);
    const $investmentValue = $calc.find("[data-ue='investment-value']");
    const $paybackValue = $calc.find("[data-ue='payback-value']");

    if (mode === UE_MODES.OWN && Number.isFinite(investment)) {
      animateNumber($investmentValue, investment, formatRub, {
        animate: animateNumbers,
        duration: animDuration,
      });
      const months = partnerProfit > 0 ? investment / partnerProfit : Number.NaN;
      animateNumber($paybackValue, months, formatMonths, {
        animate: animateNumbers,
        duration: animDuration,
      });
    } else {
      // RENT: не сбрасываем значения в "—", чтобы при анимации скрытия
      // (сужение окупаемости) не было заметного мигания текста.
      // Блок окупаемости скрывается/схлопывается CSS'ом.
    }
  }

  function initUnitEconomics() {
    const $calc = $(".ue-calc");
    if (!$calc.length) return;

    const savedSelection = loadUnitEconomicsSelection();
    const initialMode =
      savedSelection?.mode === UE_MODES.RENT
        ? UE_MODES.RENT
        : savedSelection?.mode === UE_MODES.OWN
          ? UE_MODES.OWN
          : $calc.attr("data-ue-mode") || UE_MODES.OWN;
    setUnitEconomicsMode(initialMode, true, true);

    let suppressToggleClick = false;

    $calc.find(".ue-toggle-btn").on("click", function () {
      if (suppressToggleClick) {
        suppressToggleClick = false;
        return;
      }
      const mode = $(this).data("ue-mode");
      setUnitEconomicsMode(mode);
    });

    const $toggle = $calc.find(".ue-toggle");
    if ($toggle.length) {
      const toggleEl = $toggle[0];
      let dragging = false;
      let lastRatio = 0;
      let dragStartX = 0;
      let dragMoved = false;
      let dragRect = null;

      const setDragRatio = (ratio) => {
        lastRatio = clamp01(ratio);
        toggleEl.style.setProperty("--ue-toggle-x", lastRatio);
      };

      const onPointerDown = (event) => {
        if (event.button !== undefined && event.button !== 0) return;
        dragging = true;
        dragMoved = false;
        dragStartX = event.clientX;
        dragRect = toggleEl.getBoundingClientRect();
        $toggle.addClass("is-dragging");
        toggleEl.setPointerCapture(event.pointerId);
        event.preventDefault();
      };

      const onPointerMove = (event) => {
        if (!dragging || !dragRect) return;
        if (!dragMoved && Math.abs(event.clientX - dragStartX) > 6) {
          dragMoved = true;
        }
        setDragRatio((event.clientX - dragRect.left) / dragRect.width);
      };

      const onPointerUp = (event) => {
        if (!dragging) return;
        dragging = false;
        dragRect = null;
        try {
          toggleEl.releasePointerCapture(event.pointerId);
        } catch (e) {}

        // Убираем is-dragging ПЕРЕД установкой финальной позиции, чтобы transition сработал
        $toggle.removeClass("is-dragging");

        // Определяем целевой режим
        let targetMode;
        let targetRatio;

        if (!dragMoved) {
          // Клик без перетаскивания - переключаем на противоположный режим
          const currentMode = $calc.attr("data-ue-mode");
          targetMode =
            currentMode === UE_MODES.OWN ? UE_MODES.RENT : UE_MODES.OWN;
        } else {
          // Обычное перетаскивание - используем lastRatio
          targetMode = lastRatio >= 0.5 ? UE_MODES.RENT : UE_MODES.OWN;
        }

        targetRatio = targetMode === UE_MODES.RENT ? 1 : 0;
        setDragRatio(targetRatio);

        // Удаляем переменную после завершения CSS transition
        setTimeout(() => {
          toggleEl.style.removeProperty("--ue-toggle-x");
        }, 200);

        suppressToggleClick = dragMoved;
        setUnitEconomicsMode(targetMode);
      };

      toggleEl.addEventListener("pointerdown", onPointerDown);
      toggleEl.addEventListener("pointermove", onPointerMove);
      toggleEl.addEventListener("pointerup", onPointerUp);
      toggleEl.addEventListener("pointercancel", onPointerUp);
    }

    const $priceRange = $calc.find("[data-ue='price-range']");
    const $priceInput = $calc.find("[data-ue='price-input']");
    const $monthlyRange = $calc.find("[data-ue='monthly-range']");
    const $monthlyInput = $calc.find("[data-ue='monthly-input']");
    const $priceWarning = $calc.find("[data-ue='price-warning']");
    const $monthlyWarning = $calc.find("[data-ue='monthly-warning']");

    const getWarningMessage = (rawValue, min, max, unit) => {
      if (!Number.isFinite(rawValue)) return "";
      if (Number.isFinite(min) && rawValue < min)
        return `Минимум: ${min} ${unit}`;
      if (Number.isFinite(max) && rawValue > max)
        return `Максимум: ${max} ${unit}`;
      return "";
    };

    const isWithinBounds = (rawValue, min, max) => {
      if (!Number.isFinite(rawValue)) return false;
      if (Number.isFinite(min) && rawValue < min) return false;
      if (Number.isFinite(max) && rawValue > max) return false;
      return true;
    };

    if (savedSelection) {
      const priceValue = normalizeUeValue(
        savedSelection.price,
        parseNumber($priceRange.attr("min")),
        parseNumber($priceRange.attr("max")),
        UE_DEFAULTS.price,
      );
      const monthlyValue = normalizeUeValue(
        savedSelection.monthly,
        parseNumber($monthlyRange.attr("min")),
        parseNumber($monthlyRange.attr("max")),
        UE_DEFAULTS.monthly,
      );
      $priceRange.val(priceValue);
      $priceInput.val(priceValue);
      $monthlyRange.val(monthlyValue);
      $monthlyInput.val(monthlyValue);
      setUeRangeFill($priceRange);
      setUeRangeFill($monthlyRange);
    }

    const previewPriceInput = (raw) => {
      const min = parseNumber($priceRange.attr("min"));
      const max = parseNumber($priceRange.attr("max"));
      const rawValue = parseNumber(raw);
      if (isWithinBounds(rawValue, min, max)) {
        $priceRange.val(rawValue);
      }
      setUeWarning(
        $priceWarning,
        "price",
        getWarningMessage(rawValue, min, max, "₽"),
      );
      updateUnitEconomics(state.current, {
        syncInputs: false,
        priceOverride: raw,
        animate: true,
        duration: 160,
      });
    };

    const commitPriceInput = (raw, animate = true, duration = null) => {
      const min = parseNumber($priceRange.attr("min"));
      const max = parseNumber($priceRange.attr("max"));
      const rawValue = parseNumber(raw);
      const value = normalizeUeValue(raw, min, max, UE_DEFAULTS.price);
      $priceRange.val(value);
      $priceInput.val(value);
      setUeWarning(
        $priceWarning,
        "price",
        getWarningMessage(rawValue, min, max, "₽"),
      );
      updateUnitEconomics(state.current, {
        animate,
        duration: duration || undefined,
      });
      saveUnitEconomicsSelection();
    };

    const previewMonthlyInput = (raw) => {
      const min = parseNumber($monthlyRange.attr("min"));
      const max = parseNumber($monthlyRange.attr("max"));
      const rawValue = parseNumber(raw);
      if (isWithinBounds(rawValue, min, max)) {
        $monthlyRange.val(rawValue);
      }
      setUeWarning(
        $monthlyWarning,
        "monthly",
        getWarningMessage(rawValue, min, max, "шт."),
      );
      updateUnitEconomics(state.current, {
        syncInputs: false,
        monthlyOverride: raw,
        animate: true,
        duration: 160,
      });
    };

    const commitMonthlyInput = (raw, animate = true, duration = null) => {
      const min = parseNumber($monthlyRange.attr("min"));
      const max = parseNumber($monthlyRange.attr("max"));
      const rawValue = parseNumber(raw);
      const value = normalizeUeValue(raw, min, max, UE_DEFAULTS.monthly);
      $monthlyRange.val(value);
      $monthlyInput.val(value);
      setUeWarning(
        $monthlyWarning,
        "monthly",
        getWarningMessage(rawValue, min, max, "шт."),
      );
      updateUnitEconomics(state.current, {
        animate,
        duration: duration || undefined,
      });
      saveUnitEconomicsSelection();
    };

    $priceRange.on("input", () =>
      commitPriceInput($priceRange.val(), true, 160),
    );
    $priceRange.on("change", () =>
      commitPriceInput($priceRange.val(), true, 450),
    );
    $monthlyRange.on("input", () =>
      commitMonthlyInput($monthlyRange.val(), true, 160),
    );
    $monthlyRange.on("change", () =>
      commitMonthlyInput($monthlyRange.val(), true, 450),
    );

    $priceInput.on("input", () => previewPriceInput($priceInput.val()));
    $priceInput.on("change", () =>
      commitPriceInput($priceInput.val(), true, 450),
    );
    $monthlyInput.on("input", () => previewMonthlyInput($monthlyInput.val()));
    $monthlyInput.on("change", () =>
      commitMonthlyInput($monthlyInput.val(), true, 450),
    );
  }

  function renderSpecs($block, spec) {
    if (!$block.length) return;

    const nameEl = $block.find(".spec-name");
    const listEl = $block.find(".spec-list");

    if (!spec || !spec.name) {
      $block.hide();
      nameEl.text("—");
      listEl.empty();
      return;
    }

    $block.show();
    nameEl.text(spec.name);
    listEl.empty();

    const lines = spec.specs || [];
    if (lines.length) {
      lines.forEach((line) => {
        listEl.append("<li>" + line + "</li>");
      });
    }
  }

  function populateSelect(
    $sel,
    values,
    placeholder,
    includePlaceholder = true,
  ) {
    if (!$sel.length) return;
    const uniq = Array.from(
      new Set(
        values.filter((v) => v && !skipValues.has(String(v).toLowerCase())),
      ),
    );
    const opts =
      placeholder && includePlaceholder
        ? ['<option value="">' + placeholder + "</option>"]
        : [];
    uniq.forEach((v) =>
      opts.push('<option value="' + v + '">' + v + "</option>"),
    );
    $sel.html(opts.join(""));
  }

  function populateColorSelect($sel, colorKeys, placeholder) {
    if (!$sel.length) return;
    const opts = placeholder
      ? ['<option value="">' + placeholder + "</option>"]
      : [];
    colorKeys.forEach((key) => {
      const label = COLOR_LABELS[key] || key;
      opts.push('<option value="' + key + '">' + label + "</option>");
    });
    $sel.html(opts.join(""));
  }

  function getAvailableDesignColorsForSelection() {
    const mv = $el(".cfg-select-machine").val();
    const frameVal = $el(".cfg-select-frame").val();
    const frameColorVal = $el(".cfg-select-frame-color").val();
    const fridgeVal = $el(".cfg-select-fridge").val();
    const terminalVal = $el(".cfg-select-terminal").val();
    const targetFrameColor = normalizeColorKey(frameColorVal);
    const colors = new Set();

    if (!frameVal || !frameColorVal) return [];

    state.machines.forEach((m) => {
      if (mv && normVal(m.model || m.name) !== normVal(mv)) return;
      if (frameVal && normVal(m.frame) !== normVal(frameVal)) return;
      if (
        targetFrameColor &&
        m.frame_color &&
        normalizeColorKey(m.frame_color) !== targetFrameColor
      )
        return;
      if (fridgeVal && normVal(m.refrigerator) !== normVal(fridgeVal)) return;
      if (terminalVal && normVal(m.terminal) !== normVal(terminalVal)) return;

      // Доступные цвета из design_images для выбранного цвета каркаса
      if (m.design_images && targetFrameColor) {
        Object.entries(m.design_images).forEach(([fc, inserts]) => {
          if (normalizeColorKey(fc) !== targetFrameColor) return;
          if (!inserts || typeof inserts !== "object") return;
          Object.keys(inserts).forEach((ic) => {
            const normIc = normalizeColorKey(ic);
            if (normIc && !isHiddenDesignColor(normIc)) colors.add(normIc);
          });
        });
      }

      // Цвет дизайна каркаса из таблицы (маркер наличия ссылки на Ozon)
      if (m.frame_design_color && m.ozon_link) {
        const normFd = normalizeColorKey(m.frame_design_color);
        const normFrameColor = normalizeColorKey(m.frame_color);
        if (
          (!targetFrameColor || normFrameColor === targetFrameColor) &&
          normFd &&
          !isHiddenDesignColor(normFd)
        ) {
          colors.add(normFd);
        }
      }
    });

    return Array.from(colors);
  }

  function updateTerminalState() {
    const mv = $el(".cfg-select-machine").val();
    const $t = $el(".cfg-select-terminal");
    if (!$t.length) return;
    if (!mv) {
      $t.prop("disabled", true).val("");
    } else {
      $t.prop("disabled", false);
    }
  }

  function updateInsertColorState() {
    const frameValue = ($el(".cfg-select-frame").val() || "").toLowerCase();
    const insertColorSelect = $el(".cfg-select-insert-color");
    const availableColors = getAvailableDesignColorsForSelection();

    // ✅ СОХРАНЯЕМ текущее значение ДО пересоздания селектора
    const currentValue = insertColorSelect.val();

    populateColorSelect(insertColorSelect, availableColors, null);

    if (
      !frameValue ||
      frameValue === "нет" ||
      frameValue === "no" ||
      !availableColors.length
    ) {
      if (insertColorSelect.length) {
        insertColorSelect.prop("disabled", true);
        insertColorSelect.val("");
      }
    } else {
      if (insertColorSelect.length) {
        insertColorSelect.prop("disabled", false);
        // ✅ ПРОВЕРЯЕМ сохранённое значение, а не текущее из пересозданного селектора
        const current = normalizeColorKey(currentValue);
        const hasCurrent = availableColors.some(
          (c) => normalizeColorKey(c) === current,
        );
        if (hasCurrent) {
          // ✅ Восстанавливаем сохранённое значение
          insertColorSelect.val(currentValue);
        } else {
          // Только если текущее значение недоступно - берём первое
          insertColorSelect.val(availableColors[0] || "");
        }
      }
    }
  }

  function ensureMachineSelection() {
    const $m = $el(".cfg-select-machine");
    if (!$m.length) return;
    if (!$m.val()) {
      const firstVal = $m.find("option[value!='']").first().val();
      if (firstVal) $m.val(firstVal);
    }
  }

  function ensureFridgeSelection() {
    const $f = $el(".cfg-select-fridge");
    const frameVal = $el(".cfg-select-frame").val();
    if (!$f.length) return;
    const placeholder = "Нет";

    if (frameVal) {
      $f.find("option[value='']").remove();
      if (!$f.val()) {
        const firstVal = $f.find("option").first().val();
        if (firstVal) $f.val(firstVal);
      }
    } else {
      const hasPlaceholder = $f.find(`option[value='']`).length > 0;
      if (!hasPlaceholder) {
        $f.prepend('<option value="">' + placeholder + "</option>");
      }
      if (!$f.val()) {
        $f.val("");
      }
    }
  }

  function fetchAndCacheData() {
    return $.getJSON(API_BASE + "/config-data")
      .then((res) => {
        applyLoadedData(res);
        saveCachedData(res);
        return res;
      })
      .catch(() => {
        const mReq = $.getJSON(API_BASE + "/coffee-machines");
        const sReq = $.getJSON(API_BASE + "/specs");
        return $.when(mReq, sReq).then(([m], [s]) => {
          const res = { machines: m || [], specs: s || [] };
          applyLoadedData(res);
          saveCachedData(res);
          return res;
        });
      });
  }

  function loadData() {
    const cached = loadCachedData();
    if (cached) {
      console.log("💾 Using cached configurator data");
      applyLoadedData(cached);
      fetchAndCacheData().catch(() =>
        console.warn("⚠️ Background refresh failed"),
      );
      return Promise.resolve(cached);
    }
    return fetchAndCacheData();
  }

  function renderGallery(v) {
    const $g = $el(".cfg-gallery");
    if (!$g.length) return;
    $g.empty();
  }

  function getImages(v) {
    const imgs = v.gallery_files ? v.gallery_files.map(normSrc) : [];
    const mainSrc = normSrc(
      v.main_image || (v.gallery_files && v.gallery_files[0]) || "",
    );
    if (mainSrc && !imgs.includes(mainSrc)) imgs.unshift(mainSrc);
    return imgs;
  }

  function updateMainImage(v, forceIndex) {
    const imgs = getImages(v);
    if (!$mainImg.length) return;

    const $nav = $(".cfg-image-nav");
    const $prevArrow = $nav.find(".cfg-arrow-prev");
    const $nextArrow = $nav.find(".cfg-arrow-next");

    if (!imgs.length) {
      v._imgIdx = 0;
      $mainImg.attr("src", "");
      $nav.hide();
      return;
    }

    const maxIdx = imgs.length - 1;
    const idx = Math.min(
      Math.max(forceIndex !== undefined ? forceIndex : v._imgIdx || 0, 0),
      maxIdx,
    );
    v._imgIdx = idx;
    setMainImageSrc(imgs[idx]);

    // Показываем стрелки только если больше одного изображения
    if ($nav.length) {
      if (imgs.length > 1) {
        $nav.show();
      } else {
        $nav.hide();
      }
    }
  }

  function ensureImageNav() {
    const $container = $el(".product-image");
    if (!$container.length || $container.find(".cfg-image-nav").length) return;

    if (!$container.find(".cfg-loader").length) {
      $container.append('<div class="cfg-loader"></div>');
    }

    const nav = $(`
      <div class="cfg-image-nav">
        <button type="button" class="cfg-arrow cfg-arrow-prev" aria-label="Предыдущее изображение">‹</button>
        <button type="button" class="cfg-arrow cfg-arrow-next" aria-label="Следующее изображение">›</button>
      </div>
    `);

    nav.on("click", ".cfg-arrow-prev", () => {
      const v = state.current;
      if (!v) return;
      const imgs = getImages(v);
      if (imgs.length <= 1) return;
      const nextIdx = ((v._imgIdx || 0) - 1 + imgs.length) % imgs.length;
      updateMainImage(v, nextIdx);
    });

    nav.on("click", ".cfg-arrow-next", () => {
      const v = state.current;
      if (!v) return;
      const imgs = getImages(v);
      if (imgs.length <= 1) return;
      const nextIdx = ((v._imgIdx || 0) + 1) % imgs.length;
      updateMainImage(v, nextIdx);
    });

    $container.append(nav);
  }

  function hideZoomLens() {
    $(".cfg-zoom-lens").hide();
    zoomState.pressed = false;
  }

  function updateZoomMetrics() {
    if (!$mainImg.length) return;
    const img = $mainImg[0];
    if (!img.naturalWidth || !img.naturalHeight) {
      zoomState.enabled = false;
      hideZoomLens();
      return;
    }
    const rect = img.getBoundingClientRect();
    zoomState.ratioX = img.naturalWidth / rect.width;
    zoomState.ratioY = img.naturalHeight / rect.height;
    zoomState.enabled = true;
    const bgSize = `${img.naturalWidth}px ${img.naturalHeight}px`;
    $(".cfg-zoom-lens").css("background-size", bgSize);
  }

  function updateZoomImage(src) {
    const $lens = $(".cfg-zoom-lens");
    if (!$lens.length || !src) {
      hideZoomLens();
      return;
    }
    $lens.css("background-image", src ? `url(${src})` : "none");
  }

  $(document).on("DOMContentLoaded", () => {
    $(".cfg-gallery").remove();
  });

  const $specs = $el(".specs");
  const specsOriginalParent = $specs.parent();
  const specsOriginalNext = $specs.next();
  const $productImage = $el(".product-image");
  const $mainImg = $el(".cfg-main-image");
  let imageLoadId = 0;
  const zoomState = { ratioX: 1, ratioY: 1, enabled: false, pressed: false };

  function repositionSpecs() {
    if (!$specs.length) return;
    const isMobile = window.innerWidth <= 968;

    if (isMobile) {
      if (!$specs.data("moved")) {
        $(".configurator-wrapper").after($specs);
        $specs.data("moved", true);
      }
    } else if ($specs.data("moved")) {
      if (specsOriginalNext && specsOriginalNext.length) {
        $specs.insertBefore(specsOriginalNext);
      } else {
        specsOriginalParent.append($specs);
      }
      $specs.data("moved", false);
    }
  }

  function updateImageLayout() {
    if (!$productImage.length) return;
    const frameValue = ($el(".cfg-select-frame").val() || "").toLowerCase();
    const hasFrame = !!frameValue && frameValue !== "нет";

    $productImage.toggleClass("with-frame", hasFrame);
    $productImage.toggleClass("without-frame", !hasFrame);
  }

  function setMainImageSrc(src) {
    if (!$mainImg.length || !$productImage.length) return;
    imageLoadId += 1;
    const localId = imageLoadId;

    if (!src) {
      $mainImg.attr("src", "");
      $productImage.removeClass("is-loading");
      hideZoomLens();
      return;
    }

    $productImage.addClass("is-loading");

    $mainImg.off("load.cfg error.cfg");

    $mainImg.on("load.cfg error.cfg", (e) => {
      if (localId === imageLoadId) {
        $productImage.removeClass("is-loading");
        updateZoomMetrics();
        updateZoomImage(src);
        if (e.type === "error") {
          console.warn("Image failed to load", src);
        }
      }
    });

    $mainImg.attr("src", src);
  }

  function fillSelects() {
    const m = state.machines;
    populateSelect(
      $el(".cfg-select-machine"),
      m.map((x) => x.model || x.name),
      "Нет",
      false,
    );
    populateSelect(
      $el(".cfg-select-frame"),
      m.map((x) => x.frame),
      "Нет",
    );
    populateColorSelect($el(".cfg-select-frame-color"), FRAME_COLORS, null);
    populateSelect(
      $el(".cfg-select-fridge"),
      m.map((x) => x.refrigerator),
      "Нет",
    );
    populateSelect(
      $el(".cfg-select-terminal"),
      m.map((x) => x.terminal),
      "Нет",
    );

    ensureMachineSelection();
    ensureFridgeSelection();
    updateFrameColorState();
    updateInsertColorState();
  }

  function updateFrameColorState() {
    const frameValue = $el(".cfg-select-frame").val();
    const $frameColor = $el(".cfg-select-frame-color");
    const $frameColorLabel = $frameColor
      .closest(".config-item")
      .find(".config-label");

    if (
      !frameValue ||
      frameValue === "" ||
      frameValue.toLowerCase() === "нет"
    ) {
      $frameColor.prop("disabled", true);
      $frameColorLabel.addClass("disabled-label");
      $frameColor.val("");
    } else {
      $frameColor.prop("disabled", false);
      $frameColorLabel.removeClass("disabled-label");

      if (!$frameColor.val()) {
        $frameColor.val("black");
      }
    }
  }

  function hasDesignImageForSelection(v, frameColor, insertColor) {
    if (!designImagesHasMedia(v.design_images) || !frameColor || !insertColor)
      return false;
    const found = getDesignConfig(v, frameColor, insertColor);
    return !!(
      found &&
      found.config &&
      (found.config.main_image || found.config.main_image_path)
    );
  }

  function hasAnyDesignForFrame(v, frameColor) {
    if (!designImagesHasMedia(v.design_images) || !frameColor) return false;
    const res = findDesignImageForFrame(v.design_images, frameColor);
    return !!(
      res &&
      res.config &&
      (res.config.main_image || res.config.main_image_path)
    );
  }

  function designImagesHasMedia(designImages) {
    if (!designImages || typeof designImages !== "object") return false;
    return Object.values(designImages).some((inserts) => {
      if (!inserts || typeof inserts !== "object") return false;
      return Object.values(inserts).some(
        (cfg) => cfg && (cfg.main_image || cfg.main_image_path),
      );
    });
  }

  function inferDesignImagePath(v, frameColor, insertColor) {
    if (!v || !frameColor || !insertColor) return "";
    const safeFrame = normalizeColorKey(frameColor);
    const safeInsert = normalizeColorKey(insertColor);
    if (!safeFrame || !safeInsert) return "";
    return `/static/cache/machines/${v.id}/design_${safeFrame}_${safeInsert}.webp`;
  }

  function variantScore(v, frameColor, insertColor) {
    if (hasDesignImageForSelection(v, frameColor, insertColor)) return 3;
    if (hasAnyDesignForFrame(v, frameColor)) return 2;
    if (v.main_image || (v.gallery_files && v.gallery_files.length)) return 1;
    return 0;
  }

  // ✅ ИСПРАВЛЕНО: Добавлена отладка + поддержка вариантов без каркаса
  function findOzonLinkForSelection() {
    const mv = $el(".cfg-select-machine").val();
    const fv = $el(".cfg-select-frame").val();
    const fcv = normalizeColorKey($el(".cfg-select-frame-color").val());
    const design = normalizeColorKey($el(".cfg-select-insert-color").val());
    const rv = $el(".cfg-select-fridge").val();
    const tv = $el(".cfg-select-terminal").val();

    console.log("🔍 findOzonLinkForSelection - Поиск Ozon ссылки:", {
      machine: mv,
      frame: fv,
      frameColor: fcv,
      designColor: design,
      fridge: rv,
      terminal: tv,
    });

    // ✅ ИСПРАВЛЕНО: Проверяем есть ли каркас
    const hasFrame = fv && normVal(fv) !== "нет" && normVal(fv) !== "no";

    // Если есть каркас, но нет цвета дизайна - возвращаем null
    if (hasFrame && !design) {
      console.log("⚠️ Каркас выбран, но цвет дизайна не выбран");
      return null;
    }

    // ✅ ДОБАВЛЕНО: Находим ВСЕ подходящие варианты для отладки
    const allMatches = state.machines.filter((m) => {
      if (mv && normVal(m.model || m.name) !== normVal(mv)) return false;
      if (fv && normVal(m.frame) !== normVal(fv)) return false;
      if (rv && normVal(m.refrigerator) !== normVal(rv)) return false;
      if (tv && normVal(m.terminal) !== normVal(tv)) return false;

      // ✅ ИСПРАВЛЕНО: Для вариантов без каркаса не проверяем цвета
      if (hasFrame) {
        // Для вариантов С каркасом проверяем цвета
        if (fcv && normalizeColorKey(m.frame_color) !== fcv) return false;

        const machineDesignColor = normalizeColorKey(m.frame_design_color);
        if (!m.frame_design_color || machineDesignColor !== design)
          return false;
      } else {
        // Для вариантов БЕЗ каркаса проверяем что frame_color и frame_design_color пустые
        const mFrame = normVal(m.frame);
        if (mFrame !== "нет" && mFrame !== "no" && mFrame !== "") return false;
      }

      return !!m.ozon_link;
    });

    console.log(
      `📊 Найдено ${allMatches.length} вариантов с Ozon ссылкой:`,
      allMatches.map((m) => ({
        id: m.id,
        frame: m.frame,
        frame_color: m.frame_color,
        frame_design_color: m.frame_design_color,
        ozon_link: m.ozon_link,
      })),
    );

    const candidate = allMatches[0];

    if (candidate) {
      console.log("✅ Выбран вариант:", {
        id: candidate.id,
        frame: candidate.frame,
        frame_design_color: candidate.frame_design_color,
        ozon_link: candidate.ozon_link,
      });
    } else {
      console.log("❌ Не найдено подходящих вариантов");
    }

    return candidate ? candidate.ozon_link : null;
  }

  function findVariant(allowEmpty = true) {
    const mv = $el(".cfg-select-machine").val();
    const fv = $el(".cfg-select-frame").val();
    const fcv = $el(".cfg-select-frame-color").val();
    const rv = $el(".cfg-select-fridge").val();
    const tv = $el(".cfg-select-terminal").val();
    if (!mv && allowEmpty) return null;
    const normFcv = normalizeColorKey(fcv);
    const normInsert = normalizeColorKey($el(".cfg-select-insert-color").val());

    const baseFilter = (v) => {
      if (mv && normVal(v.model || v.name) !== normVal(mv)) return false;
      if (fv && normVal(v.frame) !== normVal(fv)) return false;

      const hasDesignMediaFlag = designImagesHasMedia(v.design_images);

      if (fcv && hasDesignMediaFlag) {
        const target = normFcv;
        const hasColorWithImage = Object.entries(v.design_images).some(
          ([k, val]) => {
            if (normalizeColorKey(k) !== target) return false;
            if (!val || typeof val !== "object") return false;
            return Object.values(val).some(
              (cfg) => cfg && (cfg.main_image || cfg.main_image_path),
            );
          },
        );
        if (!hasColorWithImage) return false;
      }
      if (fcv && v.frame_color && normalizeColorKey(v.frame_color) !== normFcv)
        return false;

      if (rv && normVal(v.refrigerator) !== normVal(rv)) return false;
      if (tv && normVal(v.terminal) !== normVal(tv)) return false;
      return true;
    };

    const matchesAll = state.machines.filter(
      (v) => !excludedVariants.has(v.id) && baseFilter(v),
    );

    const designMatch = matchesAll.filter(
      (v) =>
        normInsert &&
        v.frame_design_color &&
        normalizeColorKey(v.frame_design_color) === normInsert &&
        v.ozon_link,
    );

    const exactWithImage = matchesAll.filter((v) =>
      hasDesignImageForSelection(v, normFcv, normInsert),
    );
    const exactWithFrameImage = matchesAll.filter((v) =>
      hasAnyDesignForFrame(v, normFcv),
    );

    const describe = (v) => {
      const di = v.design_images || {};
      const frameEntries = Object.entries(di).map(([k, val]) => {
        const inserts = val && typeof val === "object" ? Object.keys(val) : [];
        return `${normalizeColorKey(k)}:${inserts.length}`;
      });
      return {
        id: v.id,
        frame: v.frame,
        frame_color: v.frame_color,
        refrigerator: v.refrigerator,
        terminal: v.terminal,
        design_images: frameEntries,
      };
    };

    console.log("🔍 Candidate variants", {
      selection: { mv, fv, fcv, normFcv, normInsert, rv, tv },
      matchesAll: matchesAll.map(describe),
      withPairImage: exactWithImage.map(describe),
      withFrameImage: exactWithFrameImage.map(describe),
      designMatch: designMatch.map(describe),
    });

    if (designMatch.length) return designMatch[0];
    if (exactWithImage.length) return exactWithImage[0];
    if (exactWithFrameImage.length) return exactWithFrameImage[0];

    let cands = matchesAll;

    if (!cands.length) return allowEmpty ? null : state.machines[0] || null;

    cands = cands
      .map((v) => ({ v, score: variantScore(v, normFcv, normInsert) }))
      .sort((a, b) => b.score - a.score);

    return cands[0]?.v || cands[0];
  }

  let lastRenderedVariantId = null;

  function renderVariant(v, syncSelects = false) {
    if (!v) {
      state.current = null;
      lastRenderedVariantId = null;
      $el(".cfg-gallery").empty();
      setMainImageSrc("");
      renderSpecs($el(".cfg-spec-machine"), null);
      renderSpecs($el(".cfg-spec-frame"), null);
      renderSpecs($el(".cfg-spec-fridge"), null);
      renderSpecs($el(".cfg-spec-terminal"), null);
      updateFrameColorState();
      updateInsertColorState();
      updateImageLayout();
      updateTerminalState();
      updateUnitEconomics(null);
      return;
    }
    state.current = v;

    if (syncSelects) {
      const setSelVal = (selector, val) => {
        const $s = $el(selector);
        if ($s.length) {
          $s.val(val || "");
        }
      };
      setSelVal(".cfg-select-machine", v.model || v.name || "");
      setSelVal(".cfg-select-frame", v.frame || "");

      const frameColorMapping = {
        белый: "white",
        чёрный: "black",
        черный: "black",
      };
      const mappedFrameColor =
        frameColorMapping[v.frame_color] || v.frame_color;
      setSelVal(".cfg-select-frame-color", mappedFrameColor || "");

      setSelVal(".cfg-select-fridge", v.refrigerator || "");
      setSelVal(".cfg-select-terminal", v.terminal || "");
    }

    updateFrameColorState();
    updateInsertColorState();
    updateImageLayout();
    updateTerminalState();

    let mainSrc = "";
    let galleryFolder = v.gallery_folder;
    let usingDesignImages = false;
    const frameValue = ($el(".cfg-select-frame").val() || "").toLowerCase();
    let frameColor = normalizeColorKey($el(".cfg-select-frame-color").val());
    let insertColor = normalizeColorKey($el(".cfg-select-insert-color").val());
    const hasDesignMediaFlag = designImagesHasMedia(v.design_images);

    console.log("🎨 renderVariant Debug:", {
      machineId: v.id,
      machineName: v.name,
      frameValue,
      frameColor,
      insertColor,
      hasDesignImages: !!v.design_images,
      hasDesignMedia: hasDesignMediaFlag,
      designImagesKeys: v.design_images ? Object.keys(v.design_images) : [],
      mainImage: v.main_image,
    });

    if (
      frameValue &&
      frameValue !== "нет" &&
      frameValue !== "no" &&
      frameColor &&
      insertColor &&
      hasDesignMediaFlag
    ) {
      const designLookup = getDesignConfig(v, frameColor, insertColor);
      let designConfig = designLookup?.config;
      if (designLookup) {
        frameColor = designLookup.frameColor;
        insertColor = designLookup.insertColor;
      }

      console.log("✓ Checking design_images:", {
        frameColor,
        insertColor,
        availableFrameColors: Object.keys(v.design_images),
        foundConfig: !!designConfig,
        variantId: v.id,
      });

      if (!designConfig) {
        const fallbackDesign = findDesignImageForFrame(
          v.design_images,
          frameColor,
        );
        if (fallbackDesign) {
          designConfig = fallbackDesign.config;
          console.log("ℹ️ Falling back to available design_images combo");
        }
      }

      if (!designConfig) {
        const hasSelectedColorKey = Object.keys(v.design_images || {}).some(
          (k) => normalizeColorKey(k) === frameColor,
        );
        if (hasSelectedColorKey) {
          excludedVariants.add(v.id);
          console.warn("⛔ Skipping variant with empty design_images", {
            variantId: v.id,
            frameColor,
          });
          const alt = findVariant(true);
          if (alt && alt.id !== v.id) {
            renderVariant(alt, true);
            return;
          }
        }
      }

      if (designConfig) {
        mainSrc = normSrc(
          designConfig.main_image || designConfig.main_image_path || "",
        );
        usingDesignImages = true;
        console.log("✓ Using design_images URL:", mainSrc);
        if (designConfig.gallery_folder) {
          galleryFolder = designConfig.gallery_folder;
        }
      } else {
        console.warn(
          "⚠️ No design config found for",
          frameColor,
          "/",
          insertColor,
        );
      }
    }

    // If we have a frame selection but no design_images were provided, try an implicit path:
    // /static/cache/machines/{id}/design_{frameColor}_{insertColor}.webp
    if (
      !mainSrc &&
      frameValue &&
      frameValue !== "нет" &&
      frameValue !== "no" &&
      frameColor &&
      insertColor
    ) {
      const inferred = inferDesignImagePath(v, frameColor, insertColor);
      if (inferred) {
        mainSrc = normSrc(inferred);
        usingDesignImages = true;
        console.log("↩️ Using inferred design image path:", mainSrc);
      }
    }

    if (!mainSrc) {
      mainSrc = normSrc(
        v.main_image || (v.gallery_files && v.gallery_files[0]) || "",
      );
      console.log("📷 Using fallback main_image:", mainSrc);
    }

    const $mainImg = $el(".cfg-main-image");
    if ($mainImg.length) {
      setMainImageSrc(mainSrc || "");
      if (mainSrc) {
        updateZoomImage(mainSrc);
      } else {
        hideZoomLens();
      }
    }

    const vWithGallery = { ...v, gallery_folder: galleryFolder };

    ensureImageNav();

    if (!usingDesignImages) {
      updateMainImage(vWithGallery);
    } else {
      $(".cfg-image-nav").hide();
    }

    preloadVariantImages(v);

    const ozonBtn = $el(".cfg-btn-ozon");
    if (ozonBtn.length) {
      ozonBtn.text("Купить на OZON");

      // ✅ ИСПРАВЛЕНО: Всегда вызываем findOzonLinkForSelection
      // Она сама определит, нужна ли проверка цвета дизайна
      const ozonLink = findOzonLinkForSelection();

      if (ozonLink) {
        ozonBtn
          .removeClass("disabled")
          .removeAttr("disabled")
          .attr("href", ozonLink);
        hideOzonTooltip();
      } else {
        ozonBtn
          .addClass("disabled")
          .attr("disabled", "disabled")
          .attr("href", "#");
        showOzonTooltip();
      }
    }

    const specM = state.specs["coffee_machine"]?.[v.model || v.name] || null;
    const specF = state.specs["frame"]?.[v.frame] || null;
    const specR = state.specs["refrigerator"]?.[v.refrigerator] || null;
    const selectedTerminal = $el(".cfg-select-terminal").val();
    const specT = selectedTerminal
      ? state.specs["terminal"]?.[selectedTerminal] ||
        state.specs["terminal"]?.[v.terminal] ||
        null
      : null;

    renderSpecs($el(".cfg-spec-machine"), specM);
    renderSpecs($el(".cfg-spec-frame"), specF);
    renderSpecs($el(".cfg-spec-fridge"), specR);
    renderSpecs($el(".cfg-spec-terminal"), specT);

    saveSelection();

    // Только сбрасываем данные анимации если сменился вариант
    const variantChanged = lastRenderedVariantId !== v.id;
    if (variantChanged) {
      resetAnimationData();
      lastRenderedVariantId = v.id;
    }

    updateUnitEconomics(v, { animate: true, duration: 500 });
  }

  // OZON Tooltip функции
  function showOzonTooltip() {
    const $tooltip = $("#ozon-tooltip");
    const $emoji = $tooltip.find(".ozon-tooltip-icon");
    const $priceSection = $(".cz-conf .price-section");

    if (!$tooltip.length) return;

    // Показываем tooltip
    $tooltip.addClass("is-visible is-appearing");

    // На мобильных сдвигаем кнопки вниз
    if (window.innerWidth <= 968 && $priceSection.length) {
      $priceSection.addClass("has-tooltip");
    }

    // Анимация shrug только один раз за сессию
    if (!ozonShrugAnimationShown) {
      $emoji.addClass("is-shrugging");
      ozonShrugAnimationShown = true;
    }

    // Убираем класс появления после анимации
    setTimeout(() => {
      $tooltip.removeClass("is-appearing");
    }, 400);
  }

  function hideOzonTooltip() {
    const $tooltip = $("#ozon-tooltip");
    const $priceSection = $(".cz-conf .price-section");

    if ($tooltip.length) {
      $tooltip.removeClass("is-visible is-appearing");
    }

    // Убираем сдвиг кнопок
    if ($priceSection.length) {
      $priceSection.removeClass("has-tooltip");
    }
  }

  // Модальное окно
  function openModal() {
    $("#cfg-quote-modal").addClass("is-open");
    $("body").css("overflow", "hidden");
  }

  function closeModal() {
    $("#cfg-quote-modal").removeClass("is-open");
    $("body").css("overflow", "");
    $("#cfg-quote-form")[0].reset();
    $("#cfg-lead-consent").prop("checked", false);
    $(".cfg-lead-submit").prop("disabled", true);
    $(".cfg-form-message").removeClass("success error").hide();
  }

  function validateForm() {
    const name = $("#cfg-lead-name").val().trim();
    const phone = $("#cfg-lead-phone").val().trim();
    const consent = $("#cfg-lead-consent").is(":checked");

    const isValid = name && phone && consent;
    $(".cfg-lead-submit").prop("disabled", !isValid);
    return isValid;
  }

  function sendLead() {
    const v = state.current;
    const name = $("#cfg-lead-name").val().trim();
    const phone = $("#cfg-lead-phone").val().trim();
    const telegram = $("#cfg-lead-telegram").val().trim();
    const email = $("#cfg-lead-email").val().trim();
    const ozonLink = findOzonLinkForSelection();
    const frameValue = $el(".cfg-select-frame").val();
    const hasFrame =
      frameValue &&
      normVal(frameValue) !== "нет" &&
      normVal(frameValue) !== "no";
    const insertColorVal = $el(".cfg-select-insert-color").val();
    const insertColorKey = normalizeColorKey(insertColorVal);
    const insertColorLabel = hasFrame
      ? COLOR_LABELS[insertColorKey] || insertColorVal || ""
      : "";

    // Получаем данные из калькулятора юнит-экономики
    const $calc = $(".ue-calc");
    const ueMode = $calc.attr("data-ue-mode") || "own";
    const drinkPrice = parseNumber($calc.find("[data-ue='price-input']").val());
    const monthlyDrinks = parseNumber(
      $calc.find("[data-ue='monthly-input']").val(),
    );

    // Добавляем данные юнит-экономики в сообщение (не меняя логику отправки)
    const modeKey = ueMode === UE_MODES.RENT ? UE_MODES.RENT : UE_MODES.OWN;
    const modeLabel =
      modeKey === UE_MODES.RENT
        ? "Аренда оборудования"
        : "Оборудование в собственности";
    const share = UE_SHARES[modeKey] || UE_SHARES.own;

    const $priceRange = $calc.find("[data-ue='price-range']");
    const $monthlyRange = $calc.find("[data-ue='monthly-range']");
    const priceMin = parseNumber($priceRange.attr("min"));
    const priceMax = parseNumber($priceRange.attr("max"));
    const monthlyMin = parseNumber($monthlyRange.attr("min"));
    const monthlyMax = parseNumber($monthlyRange.attr("max"));

    const priceNorm = normalizeUeValue(
      drinkPrice,
      priceMin,
      priceMax,
      UE_DEFAULTS.price,
    );
    const monthlyNorm = normalizeUeValue(
      monthlyDrinks,
      monthlyMin,
      monthlyMax,
      UE_DEFAULTS.monthly,
    );

    const gross = priceNorm * monthlyNorm;
    const net = gross * 0.97;
    const partnerProfit = net * share.partner;
    const companyProfit = net * share.company;
    const perDay = monthlyNorm / 30;

    const investment = parseNumber(v && v.price);
    const paybackMonths =
      modeKey === UE_MODES.OWN &&
      Number.isFinite(investment) &&
      partnerProfit > 0
        ? investment / partnerProfit
        : Number.NaN;

    const ueText = [
      "Юнит-экономика:",
      `• Режим: ${modeLabel}`,
      `• Стоимость напитка: ${formatRub(priceNorm)}`,
      `• Напитков в месяц: ${Math.round(monthlyNorm).toLocaleString("ru-RU")} шт.`,
      `• Напитков в день: ${formatCount(perDay)} шт.`,
      `• Выручка в месяц: ${formatRub(gross)}`,
      `• Чистая выручка: ${formatRub(net)}`,
      `• Партнер: ${Math.round(share.partner * 100)}% (${formatRub(partnerProfit)})`,
      `• Франшиза: ${Math.round(share.company * 100)}% (${formatRub(companyProfit)})`,
      modeKey === UE_MODES.OWN
        ? `• Окупаемость: ${formatMonths(paybackMonths)}`
        : null,
    ]
      .filter(Boolean)
      .join("\n");

    // ВАЖНО: бэкенд сейчас выводит в Telegram только блок selection,
    // поэтому добавляем юнит-экономику в поле цены (которое точно показывается).
    const leadPrice =
      (Number.isFinite(investment)
        ? formatRub(investment)
        : v && v.price
          ? String(v.price)
          : "") +
      "\n" +
      ueText;

    const payload = {
      name: name,
      phone: phone,
      telegram: telegram || "",
      email: email || "",
      selection: v
        ? {
            id: v.id,
            machine: v.model || v.name,
            frame: v.frame,
            frame_color: v.frame_color,
            insert_color: insertColorLabel,
            refrigerator: v.refrigerator,
            terminal: v.terminal,
            price: leadPrice,
            ozon_link: ozonLink,
            gallery_folder: v.gallery_folder,
          }
        : null,
      unit_economics: {
        mode:
          ueMode === "rent"
            ? "Аренда оборудования"
            : "Оборудование в собственности",
        drink_price: drinkPrice,
        monthly_drinks: monthlyDrinks,
      },
    };

    return $.ajax({
      url: LEAD_ENDPOINT,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify(payload),
    });
  }

  // Генерация PDF с текстовым слоем
  async function generatePDF() {
    const v = state.current;
    if (!v) {
      alert("Сначала выберите конфигурацию");
      return;
    }

    const ozonLink = findOzonLinkForSelection();

    // Показываем индикатор загрузки
    const $btn = $(".cfg-btn-pdf");
    const originalText = $btn.html();
    $btn.html("<span>...</span>").prop("disabled", true);

    try {
      const { jsPDF } = window.jspdf;

      const doc = new jsPDF({
        orientation: "landscape",
        unit: "mm",
        format: "a4",
      });

      // Загружаем локальный кириллический шрифт (Roboto TTF)
      let fontLoaded = false;

      try {
        const inlineReg = window.CZ_FONT_REG_BASE64;
        const inlineBold = window.CZ_FONT_BOLD_BASE64;

        if (inlineReg && inlineBold) {
          try {
            doc.addFileToVFS("Roboto-Regular.ttf", inlineReg);
            doc.addFont("Roboto-Regular.ttf", "Roboto", "normal");

            doc.addFileToVFS("Roboto-Bold.ttf", inlineBold);
            doc.addFont("Roboto-Bold.ttf", "Roboto", "bold");

            fontLoaded = true;
            console.log("Шрифты загружены из встроенных base64");
          } catch (errInline) {
            console.warn(
              "Встроенные base64-шрифты невалидны, пробуем загрузить файлы:",
              errInline
            );
            fontLoaded = false;
          }
        }

        if (!fontLoaded) {
          // Локальные шрифты из папки fonts/
          const fontUrl = assetUrl("fonts/Roboto-Regular.ttf");
          const fontBoldUrl = assetUrl("fonts/Roboto-Bold.ttf");

          const [fontResp, fontBoldResp] = await Promise.all([
            fetch(fontUrl),
            fetch(fontBoldUrl),
          ]);

          if (fontResp.ok && fontBoldResp.ok) {
            const fontBuffer = await fontResp.arrayBuffer();
            const fontBoldBuffer = await fontBoldResp.arrayBuffer();

            // Конвертируем в base64
            const fontBase64 = arrayBufferToBase64(fontBuffer);
            const fontBoldBase64 = arrayBufferToBase64(fontBoldBuffer);

            doc.addFileToVFS("Roboto-Regular.ttf", fontBase64);
            doc.addFont("Roboto-Regular.ttf", "Roboto", "normal");

            doc.addFileToVFS("Roboto-Bold.ttf", fontBoldBase64);
            doc.addFont("Roboto-Bold.ttf", "Roboto", "bold");

            fontLoaded = true;
            console.log("Шрифты загружены успешно");
          } else {
            console.warn(
              "Не удалось загрузить шрифты. Убедитесь что файлы Roboto-Regular.ttf и Roboto-Bold.ttf находятся в папке fonts/"
            );
          }
        }
      } catch (e) {
        console.warn("Ошибка загрузки шрифтов:", e);
        console.warn(
          "Убедитесь что файлы Roboto-Regular.ttf и Roboto-Bold.ttf находятся в папке fonts/"
        );
      }

      let useFont = fontLoaded ? "Roboto" : "helvetica";
      // Если по какой-то причине шрифт не зарегистрирован (Tilda может резать инлайн),
      // переключаемся на встроенный helvetica, чтобы не падать на splitTextToSize.
      const fontList = doc.getFontList() || {};
      if (!fontList[useFont]) {
        console.warn(
          `Font ${useFont} is not available, falling back to helvetica`
        );
        useFont = "helvetica";
      }
      const pageWidth = 297;
      const pageHeight = 210;
      const margin = 15;

      // Получаем спецификации из DOM
      const getSpecFromDOM = (selector) => {
        const $block = $(selector);
        if (!$block.length || $block.is(":hidden")) return null;
        const name = $block.find(".spec-name").text().trim();
        const specs = [];
        $block.find(".spec-list li").each(function () {
          specs.push($(this).text().trim());
        });
        return { name, specs };
      };

      const machineSpec = getSpecFromDOM(".cfg-spec-machine");
      const fridgeSpec = getSpecFromDOM(".cfg-spec-fridge");
      const frameSpec = getSpecFromDOM(".cfg-spec-frame");
      const terminalSpec = getSpecFromDOM(".cfg-spec-terminal");

      const frameColorVal = $el(".cfg-select-frame-color").val();
      const insertColorVal = $el(".cfg-select-insert-color").val();
      const frameColorLabel =
        COLOR_LABELS[frameColorVal] || frameColorVal || "";
      const insertColorLabel =
        COLOR_LABELS[insertColorVal] || insertColorVal || "";
      const priceText = v.price
        ? Number(v.price).toLocaleString("ru-RU") + " RUB"
        : "Цена по запросу";

      // Заголовок
      doc.setFont(useFont, "bold");
      doc.setFontSize(24);
      doc.setTextColor(0, 100, 252);
      doc.text("COFFEE ZONE", pageWidth / 2, 18, { align: "center" });

      // Линия под заголовком
      doc.setDrawColor(0, 100, 252);
      doc.setLineWidth(0.5);
      doc.line(margin, 22, pageWidth - margin, 22);

      // Загружаем и добавляем картинку
      const imgSrc = $el(".cfg-main-image").attr("src");
      const imgAreaX = margin;
      const imgAreaY = 28;
      const imgAreaW = 95;
      const imgAreaH = 120;

      // Фон для картинки
      doc.setFillColor(247, 247, 247);
      doc.roundedRect(imgAreaX, imgAreaY, imgAreaW, imgAreaH, 3, 3, "F");

      if (imgSrc) {
        try {
          const imgData = await loadImageAsBase64(imgSrc);
          if (imgData) {
            doc.addImage(
              imgData,
              "PNG",
              imgAreaX + 5,
              imgAreaY + 5,
              imgAreaW - 10,
              imgAreaH - 10,
              undefined,
              "FAST"
            );
          }
        } catch (e) {
          console.warn("Не удалось добавить изображение:", e);
        }
      }

      // Цена под картинкой
      const priceY = imgAreaY + imgAreaH + 8;
      doc.setFillColor(0, 100, 252);
      doc.roundedRect(imgAreaX, priceY, imgAreaW, 14, 2, 2, "F");
      doc.setFont(useFont, "bold");
      doc.setFontSize(16);
      doc.setTextColor(255, 255, 255);
      doc.text(priceText, imgAreaX + imgAreaW / 2, priceY + 9.5, {
        align: "center",
      });

      // Цвета под ценой
      if (frameColorLabel || insertColorLabel) {
        doc.setFont(useFont, "normal");
        doc.setFontSize(8);
        doc.setTextColor(0, 0, 0);
        let colorY = priceY + 20;
        if (frameColorLabel) {
          doc.text("Цвет каркаса: " + frameColorLabel, imgAreaX, colorY);
          colorY += 4;
        }
        if (insertColorLabel) {
          doc.text("Цвет дизайна: " + insertColorLabel, imgAreaX, colorY);
        }
      }

      // Правая часть - спецификации
      const specStartX = imgAreaX + imgAreaW + 10;
      const specWidth = (pageWidth - specStartX - margin) / 2 - 5;
      let specY = 30;

      doc.setFont(useFont, "bold");
      doc.setFontSize(12);
      doc.setTextColor(0, 0, 0);
      doc.text("Спецификации", specStartX, specY);

      doc.setDrawColor(200, 200, 200);
      doc.setLineWidth(0.2);
      doc.line(specStartX, specY + 2, pageWidth - margin, specY + 2);

      specY += 8;

      // Функция отрисовки блока спецификаций
      const drawSpecBlock = (spec, title, x, startY, maxWidth) => {
        if (
          !spec ||
          !spec.name ||
          ["-", "—", "–"].includes(String(spec.name).trim())
        )
          return startY;

        let y = startY;

        // Заголовок
        doc.setFont(useFont, "normal");
        doc.setFontSize(7);
        doc.setTextColor(150, 150, 150);
        doc.text(title.toUpperCase(), x, y);
        y += 4;

        // Название
        doc.setFont(useFont, "bold");
        doc.setFontSize(9);
        doc.setTextColor(0, 0, 0);
        const nameLines = doc.splitTextToSize(spec.name, maxWidth);
        doc.text(nameLines, x, y);
        y += nameLines.length * 4 + 2;

        // Характеристики
        doc.setFont(useFont, "normal");
        doc.setFontSize(7);
        doc.setTextColor(60, 60, 60);

        spec.specs.forEach((line) => {
          const text = "• " + line;
          const lines = doc.splitTextToSize(text, maxWidth);
          doc.text(lines, x, y);
          y += lines.length * 3;
        });

        return y + 4;
      };

      // Левая колонка спецификаций
      let leftY = specY;
      leftY = drawSpecBlock(
        machineSpec,
        "Кофемашина",
        specStartX,
        leftY,
        specWidth
      );
      leftY = drawSpecBlock(frameSpec, "Каркас", specStartX, leftY, specWidth);

      // Правая колонка спецификаций
      const rightX = specStartX + specWidth + 10;
      let rightY = specY;
      rightY = drawSpecBlock(
        fridgeSpec,
        "Холодильник",
        rightX,
        rightY,
        specWidth
      );
      rightY = drawSpecBlock(
        terminalSpec,
        "Терминал",
        rightX,
        rightY,
        specWidth
      );

      // Ссылки с QR-кодами под спецификациями
      const linksY = Math.max(leftY, rightY) + 5;
      doc.setDrawColor(200, 200, 200);
      doc.line(specStartX, linksY, pageWidth - margin, linksY);

      const qrSize = 25;
      const linkBlockWidth = 70;

      // Telegram
      const tgLink = "https://t.me/coffeezone_ru";
      const tgX = specStartX;
      const tgY = linksY + 5;

      doc.setFont(useFont, "bold");
      doc.setFontSize(9);
      doc.setTextColor(0, 0, 0);
      doc.text("Telegram", tgX, tgY);

      doc.setFont(useFont, "normal");
      doc.setFontSize(7);
      doc.setTextColor(0, 100, 252);
      doc.textWithLink(tgLink, tgX, tgY + 4, { url: tgLink });

      // QR для Telegram
      try {
        const tgQR = await generateQRCode(tgLink);
        if (tgQR) {
          doc.addImage(tgQR, "PNG", tgX, tgY + 7, qrSize, qrSize);
        }
      } catch (e) {
        console.warn("Не удалось создать QR для Telegram:", e);
      }

      // OZON (если есть)
      if (ozonLink) {
        const ozonX = tgX + linkBlockWidth;
        const ozonY = tgY;

        doc.setFont(useFont, "bold");
        doc.setFontSize(9);
        doc.setTextColor(0, 0, 0);
        doc.text("OZON", ozonX, ozonY);

        doc.setFont(useFont, "normal");
        doc.setFontSize(7);
        doc.setTextColor(0, 100, 252);
        const ozonShort =
          ozonLink.length > 35
            ? ozonLink.substring(0, 35) + "..."
            : ozonLink;
        doc.textWithLink(ozonShort, ozonX, ozonY + 4, { url: ozonLink });

        // QR для OZON
        try {
          const ozonQR = await generateQRCode(ozonLink);
          if (ozonQR) {
            doc.addImage(ozonQR, "PNG", ozonX, ozonY + 7, qrSize, qrSize);
          }
        } catch (e) {
          console.warn("Не удалось создать QR для OZON:", e);
        }
      }

      // Футер
      doc.setFont(useFont, "normal");
      doc.setFontSize(8);
      doc.setTextColor(150, 150, 150);
      doc.text(
        "coffeezone.ru | " + new Date().toLocaleDateString("ru-RU"),
        pageWidth / 2,
        pageHeight - 10,
        { align: "center" }
      );

      // Скачиваем
      const fileName =
        "coffeezone-" +
        (v.model || v.name || "config")
          .replace(/[^a-zA-Z0-9а-яА-ЯёЁ]/g, "-")
          .toLowerCase() +
        ".pdf";
      doc.save(fileName);
    } catch (err) {
      console.error("Ошибка генерации PDF:", err);
      alert("Не удалось создать PDF: " + err.message);
    } finally {
      $btn.html(originalText).prop("disabled", false);
    }
  }

  // Генерация QR-кода как base64 изображения
  function generateQRCode(text) {
    return new Promise((resolve) => {
      try {
        // Создаём временный контейнер
        const container = document.createElement("div");
        container.style.position = "absolute";
        container.style.left = "-9999px";
        document.body.appendChild(container);

        // Генерируем QR
        const qr = new QRCode(container, {
          text: text,
          width: 128,
          height: 128,
          colorDark: "#000000",
          colorLight: "#ffffff",
          correctLevel: QRCode.CorrectLevel.M,
        });

        // Ждём рендера и получаем canvas
        setTimeout(() => {
          const canvas = container.querySelector("canvas");
          if (canvas) {
            const dataUrl = canvas.toDataURL("image/png");
            document.body.removeChild(container);
            resolve(dataUrl);
          } else {
            document.body.removeChild(container);
            resolve(null);
          }
        }, 100);
      } catch (e) {
        console.warn("Ошибка генерации QR:", e);
        resolve(null);
      }
    });
  }

  // Конвертация ArrayBuffer в Base64
  function arrayBufferToBase64(buffer) {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  // Вспомогательная функция загрузки картинки как base64
  function loadImageAsBase64(src) {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = function () {
        try {
          const canvas = document.createElement("canvas");
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          const ctx = canvas.getContext("2d");
          ctx.fillStyle = "#F7F7F7";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0);
          resolve(canvas.toDataURL("image/png"));
        } catch (e) {
          console.warn("Canvas error:", e);
          resolve(null);
        }
      };
      img.onerror = () => resolve(null);
      img.src = src + (src.includes("?") ? "&" : "?") + "t=" + Date.now();
    });
  }

  function bindEvents() {
    // ✅ ИСПРАВЛЕНО: Разделяем обработчики для разных селекторов
    // При изменении этих полей обновляем состояние цвета дизайна
    $(
      ".cfg-select-machine, .cfg-select-frame, .cfg-select-frame-color, .cfg-select-fridge, .cfg-select-terminal"
    ).on("change", () => {
      ensureMachineSelection();
      ensureFridgeSelection();
      updateFrameColorState();
      updateInsertColorState(); // Обновляем доступные цвета дизайна
      updateImageLayout();
      renderVariant(findVariant(true));
    });

    // При изменении самого цвета дизайна НЕ вызываем updateInsertColorState
    $(".cfg-select-insert-color").on("change", () => {
      updateImageLayout();
      renderVariant(findVariant(true));
    });

    $(window).on("resize", repositionSpecs);

    // PDF кнопка
    $el(".cfg-btn-pdf").on("click", (e) => {
      e.preventDefault();
      generatePDF();
    });

    $el(".cfg-btn-quote").on("click", (e) => {
      e.preventDefault();
      openModal();
    });

    $(".cfg-modal-close, .cfg-modal-overlay").on("click", (e) => {
      e.preventDefault();
      closeModal();
    });

    $("#cfg-lead-name, #cfg-lead-phone, #cfg-lead-consent").on(
      "input change",
      validateForm
    );

    $("#cfg-quote-form").on("submit", (e) => {
      e.preventDefault();

      if (!validateForm()) {
        return;
      }

      const $submitBtn = $(".cfg-lead-submit");
      const $message = $(".cfg-form-message");

      $submitBtn.prop("disabled", true).text("Отправка...");
      $message.removeClass("success error").hide();

      sendLead()
        .done(() => {
          $message
            .addClass("success")
            .text("Заявка успешно отправлена!")
            .show();
          setTimeout(() => {
            closeModal();
          }, 2000);
        })
        .fail(() => {
          $message
            .addClass("error")
            .text("Не удалось отправить заявку. Попробуйте ещё раз.")
            .show();
          $submitBtn.prop("disabled", false).text("Отправить");
        });
    });

    const isCoarsePointer =
      window.matchMedia &&
      window.matchMedia("(hover: none) and (pointer: coarse)").matches;
    if (isCoarsePointer) {
      const tapClass = "is-tap";
      $(".ue-kpi").on("pointerdown touchstart", function () {
        const $kpi = $(this);
        $kpi.removeClass(tapClass);
        // Force reflow to restart the CSS animation.
        void this.offsetWidth;
        $kpi.addClass(tapClass);
        setTimeout(() => $kpi.removeClass(tapClass), 950);
      });
    }
  }

  // Инициализация
  $(document).ready(function () {
    loadData()
      .then(() => {
        fillSelects();

        const saved = loadSelection();
        if (saved) {
          $el(".cfg-select-machine").val(saved.machine || "");
          $el(".cfg-select-frame").val(saved.frame || "");
          $el(".cfg-select-frame-color").val(saved.frame_color || "");
          $el(".cfg-select-insert-color").val(saved.insert_color || "");
          $el(".cfg-select-fridge").val(saved.fridge || "");
          $el(".cfg-select-terminal").val(saved.terminal || "");
        }

        ensureMachineSelection();
        ensureFridgeSelection();
        updateFrameColorState();
        updateInsertColorState();
        updateTerminalState();
        initUnitEconomics();

        let initialVariant = findVariant(true);
        let syncSelects = false;
        if (!initialVariant && state.machines.length) {
          initialVariant = state.machines[0];
          syncSelects = true;
        }
        renderVariant(initialVariant, syncSelects);
        bindEvents();
        repositionSpecs();
        updateImageLayout();

        setTimeout(() => {
          state.machines.slice(0, 5).forEach((machine) => {
            preloadVariantImages(machine);
          });
        }, 500);
        hideInitialLoader();
      })
      .catch(() => console.error("Не удалось загрузить конфигуратор"))
      .finally(() => hideInitialLoader());
  });
})(jQuery);

(function () {
  const btn = document.querySelector(".cz-conf .cfg-btn-quote");
  if (!btn) return;

  const reduceMotion = window.matchMedia?.(
    "(prefers-reduced-motion: reduce)",
  )?.matches;
  if (reduceMotion) return;

  // Пауза, чтобы пользователь успел ознакомиться
  const START_AFTER_MS = 9000; // 9 секунд
  // Случайные интервалы между "подмигиваниями"
  const MIN_INTERVAL_MS = 9000; // минимум 9с
  const MAX_INTERVAL_MS = 18000; // максимум 18с

  let stopped = false;
  let timer = null;

  const rand = (min, max) => Math.floor(min + Math.random() * (max - min));

  function pulse() {
    if (stopped) return;

    // запустить эффект
    btn.classList.add("is-nudge");
    // снять класс после окончания (shine 900ms, дрожь 250ms)
    setTimeout(() => btn.classList.remove("is-nudge"), 950);

    timer = setTimeout(pulse, rand(MIN_INTERVAL_MS, MAX_INTERVAL_MS));
  }

  function stopNudges() {
    if (stopped) return;
    stopped = true;
    if (timer) clearTimeout(timer);
    btn.classList.remove("is-nudge");
    // на всякий случай: не "дергать" больше событиями
    window.removeEventListener("scroll", stopNudges, { passive: true });
    document.removeEventListener("pointerdown", onPointerDown, true);
    document.removeEventListener("keydown", stopNudges, true);
  }

  function onPointerDown(e) {
    // как только человек взаимодействует со страницей — прекращаем
    // (можно оставить только на клик по кнопке, если хотите)
    stopNudges();
  }

  // Старт через паузу (и только если пользователь уже что-то не сделал)
  setTimeout(() => {
    if (stopped) return;
    pulse();
  }, START_AFTER_MS);

  // Останавливаем при взаимодействии пользователя
  window.addEventListener("scroll", stopNudges, { passive: true });
  document.addEventListener("pointerdown", onPointerDown, true);
  document.addEventListener("keydown", stopNudges, true);

  // И точно останавливаем после клика по кнопке
  btn.addEventListener("click", stopNudges, { passive: true });
})();
