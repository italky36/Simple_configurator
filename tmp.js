
(function ($) {
  // Используем текущий origin, чтобы фронт и бэкенд на одном хосте работали без правок.
  // Фолбэк на локальный порт 8070 для запуска прямо с сервера.
  const BACKEND_BASE = (window.location && window.location.origin ? window.location.origin.replace(/\/$/, "") : "") || "http://127.0.0.1:8070";
  const API_BASE = BACKEND_BASE + "/api";
  const LEAD_ENDPOINT = API_BASE + "/lead";

  const state = { machines: [], specs: {}, current: null };
  const skipValues = new Set(["нет", "не", "-", "none", "", null, undefined]);
  const STORAGE_KEY = "cz-conf-selection";
  const DATA_CACHE_KEY = "cz-conf-cache-v1";
  const CACHE_TTL_MS = Infinity; // бессрочный кеш: не очищаем автоматически

  // Цвета: английские ключи для данных (используются как value в select)
  const FRAME_COLORS = ["white", "black"];
  const INSERT_COLORS = ["yellow", "green", "red", "gray", "blue", "purple"];

  // Маппинг английских ключей на русские названия для отображения
  const COLOR_LABELS = {
    "white": "Белый",
    "black": "Чёрный",
    "yellow": "Жёлтый",
    "green": "Зелёный",
    "red": "Красный",
    "gray": "Серый",
    "blue": "Синий",
    "purple": "Фиолетовый"
  };

  // Кеш предзагруженных изображений для быстрой смены
  const imageCache = new Map();
  const normalizeColorKey = (key) => {
    if (!key) return "";
    const k = String(key).trim().toLowerCase();
    const map = {
      "white": "white",
      "белый": "white",
      "белая": "white",
      "бел": "white",
      "black": "black",
      "чёрный": "black",
      "черный": "black",
      "черная": "black",
      "yellow": "yellow",
      "желтый": "yellow",
      "желтая": "yellow",
      "green": "green",
      "зеленый": "green",
      "зеленая": "green",
      "red": "red",
      "красный": "red",
      "красная": "red",
      "gray": "gray",
      "серый": "gray",
      "серая": "gray",
      "grey": "gray",
      "blue": "blue",
      "синий": "blue",
      "синяя": "blue",
      "purple": "purple",
      "фиолетовый": "purple",
      "фиолетовая": "purple",
    };
    return map[k] || k;
  };

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

    // Предзагружаем основное изображение
    if (v.main_image) {
      imagesToPreload.push(normSrc(v.main_image));
    }

    // Предзагружаем все design_images для текущего варианта
    if (v.design_images) {
      Object.values(v.design_images).forEach(frameColors => {
        Object.values(frameColors).forEach(config => {
          if (config.main_image || config.main_image_path) {
            imagesToPreload.push(normSrc(config.main_image || config.main_image_path));
          }
        });
      });
    }

    // Запускаем предзагрузку всех изображений
    imagesToPreload.forEach(src => preloadImage(src));
  }

  const $el = (cls) => $(cls).first();
  const setText = (jq, txt) => jq.length && jq.text(txt || "—");
  const fmtPrice = (v) => (v || v === 0 ? Number(v).toLocaleString("ru-RU") + " ₽" : "—");
  const normSrc = (src) => {
    if (!src) return "";
    if (/^(https?:)?\/\//i.test(src) || src.startsWith("data:")) return src;
    const base = BACKEND_BASE.replace(/\/+$/, "");
    const path = src.startsWith("/") ? src : "/" + src;
    return base + path;
  };
  const normVal = (v) => (v === null || v === undefined ? "" : String(v).trim().toLowerCase());
  const showInitialLoader = () => $(".cfg-initial-loader").removeClass("is-hidden");
  const hideInitialLoader = () => $(".cfg-initial-loader").addClass("is-hidden");

  function applyLoadedData(res) {
    state.machines = res?.machines || [];
    state.specs = {};
    (res?.specs || []).forEach((sp) => {
      if (!state.specs[sp.category]) state.specs[sp.category] = {};
      state.specs[sp.category][sp.name] = sp;
    });
    console.log("📡 Loaded machines:", state.machines.length);
    state.machines.forEach(m => {
      if (m.design_images) {
        console.log(`  Machine ${m.id} (${m.name}) has design_images:`, Object.keys(m.design_images));
      }
    });
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
      localStorage.setItem(DATA_CACHE_KEY, JSON.stringify({ timestamp: Date.now(), data }));
    } catch (e) {
      // ignore quota errors
    }
  }

  // Варианты, которые уже доказали, что по выбранному цвету каркаса у них пустой набор картинок
  const excludedVariants = new Set();

  // Ищем первый доступный набор картинок в design_images, чтобы не упасть на пустых ключах
  function findFirstDesignImageConfig(designImages) {
    if (!designImages) return null;
    for (const [frameColorKey, inserts] of Object.entries(designImages)) {
      const normFrame = normalizeColorKey(frameColorKey);
      if (!inserts || typeof inserts !== "object" || !Object.keys(inserts).length) continue;
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

  // Ищем первую доступную вставку в рамках выбранного цвета каркаса
  function findDesignImageForFrame(designImages, frameColorKey) {
    if (!designImages || !frameColorKey) return null;
    const normFrame = normalizeColorKey(frameColorKey);
    const inserts = Object.entries(designImages).find(
      ([key]) => normalizeColorKey(key) === normFrame
    )?.[1];
    if (!inserts || typeof inserts !== "object" || !Object.keys(inserts).length) return null;
    for (const [insertColorKey, cfg] of Object.entries(inserts)) {
      const normInsert = normalizeColorKey(insertColorKey);
      if (cfg && (cfg.main_image || cfg.main_image_path)) {
        return { frameColor: normFrame || frameColorKey, insertColor: normInsert || insertColorKey, config: cfg };
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
    } catch (e) {
      // ignore quota / private mode errors
    }
  }

  function loadSelection() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function renderSpecs($block, spec) {
    if (!$block.length) return;

    const nameEl = $block.find('.spec-name');
    const listEl = $block.find('.spec-list');

    if (!spec || !spec.name) {
      $block.hide();
      nameEl.text('—');
      listEl.empty();
      return;
    }

    $block.show();
    nameEl.text(spec.name);
    listEl.empty();

    const lines = spec.specs || [];
    if (lines.length) {
      lines.forEach(line => {
        listEl.append('<li>' + line + '</li>');
      });
    }
  }

  function populateSelect($sel, values, placeholder, includePlaceholder = true) {
    if (!$sel.length) return;
    const uniq = Array.from(new Set(values.filter((v) => v && !skipValues.has(String(v).toLowerCase()))));
    const opts = placeholder && includePlaceholder ? ['<option value="">' + placeholder + '</option>'] : [];
    uniq.forEach((v) => opts.push('<option value="' + v + '">' + v + '</option>'));
    $sel.html(opts.join(""));
  }

  // Заполнение селекта цветов: value = английский ключ, text = русское название
  function populateColorSelect($sel, colorKeys, placeholder) {
    if (!$sel.length) return;
    const opts = placeholder ? ['<option value="">' + placeholder + '</option>'] : [];
    colorKeys.forEach((key) => {
      const label = COLOR_LABELS[key] || key;
      opts.push('<option value="' + key + '">' + label + '</option>');
    });
    $sel.html(opts.join(""));
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

    if (!frameValue || frameValue === "нет" || frameValue === "no") {
      if (insertColorSelect.length) {
        insertColorSelect.prop("disabled", true);
        insertColorSelect.val("");
      }
    } else {
      if (insertColorSelect.length) {
        insertColorSelect.prop("disabled", false);
        if (!insertColorSelect.val()) {
          insertColorSelect.val("blue");  // Английский ключ вместо русского
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
    const placeholder = "Выберите холодильник";

    if (frameVal) {
      // убираем placeholder и выставляем первый доступный, если не выбрано
      $f.find("option[value='']").remove();
      if (!$f.val()) {
        const firstVal = $f.find("option").first().val();
        if (firstVal) $f.val(firstVal);
      }
    } else {
      // возвращаем placeholder, если его нет
      const hasPlaceholder = $f.find(`option[value='']`).length > 0;
      if (!hasPlaceholder) {
        $f.prepend('<option value="">' + placeholder + '</option>');
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
        // Фолбэк: два лёгких запроса, без include_gallery
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
      // Обновляем фоновой загрузкой, но не блокируем первичный рендер
      fetchAndCacheData().catch(() => console.warn("⚠️ Background refresh failed"));
      return Promise.resolve(cached);
    }
    return fetchAndCacheData();
  }

  // Галерея превью скрыта, поэтому функция просто очищает контейнер (для совместимости).
  function renderGallery(v) {
    const $g = $el(".cfg-gallery");
    if (!$g.length) return;
    $g.empty();
  }

  function getImages(v) {
    const imgs = v.gallery_files ? v.gallery_files.map(normSrc) : [];
    const mainSrc = normSrc(v.main_image || (v.gallery_files && v.gallery_files[0]) || "");
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
    const idx = Math.min(Math.max(forceIndex !== undefined ? forceIndex : (v._imgIdx || 0), 0), maxIdx);
    v._imgIdx = idx;
    setMainImageSrc(imgs[idx]);

    if ($nav.length) {
      $nav.show();
      // Если одно фото — стрелки неактивны
      if (imgs.length <= 1) {
        $prevArrow.addClass("disabled").prop("disabled", true);
        $nextArrow.addClass("disabled").prop("disabled", true);
      } else {
        $prevArrow.removeClass("disabled").prop("disabled", false);
        $nextArrow.removeClass("disabled").prop("disabled", false);
      }
    }
  }

  function ensureImageNav() {
    const $container = $el(".product-image");
    if (!$container.length || $container.find(".cfg-image-nav").length) return;

    // Добавляем спиннер при первой инициализации
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

    // Лупа временно отключена
  }

  function ensureZoomLens() {
    const $container = $el(".product-image");
    if (!$container.length || $container.find(".cfg-zoom-lens").length) return;
    $container.append('<div class="cfg-zoom-lens"></div>');
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

  function triggerVibration() {
    try {
      if (navigator.vibrate) navigator.vibrate(12);
    } catch (e) {
      // ignore vibration errors
    }
  }

  function getPointerCoords(evt) {
    if (evt.touches && evt.touches.length) {
      return { clientX: evt.touches[0].clientX, clientY: evt.touches[0].clientY };
    }
    if (evt.changedTouches && evt.changedTouches.length) {
      return { clientX: evt.changedTouches[0].clientX, clientY: evt.changedTouches[0].clientY };
    }
    if (evt.clientX !== undefined && evt.clientY !== undefined) {
      return { clientX: evt.clientX, clientY: evt.clientY };
    }
    return null;
  }

  function setupZoomHandlers() {
    // Zoom / loupe is temporarily disabled
    return;
    const $lens = $(".cfg-zoom-lens");
    if (!$productImage.length || !$lens.length || !$mainImg.length) return;

    const move = (evt) => {
      const point = getPointerCoords(evt);
      if (!point) return hideZoomLens();
      if (!zoomState.enabled || !zoomState.pressed) return hideZoomLens();
      const rect = $mainImg[0].getBoundingClientRect();
      const x = point.clientX - rect.left;
      const y = point.clientY - rect.top;
      if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
        hideZoomLens();
        return;
      }

      const half = ZOOM_LENS_SIZE / 2;
      const lensLeft = Math.max(rect.left, Math.min(rect.right - ZOOM_LENS_SIZE, evt.clientX - half));
      const lensTop = Math.max(rect.top, Math.min(rect.bottom - ZOOM_LENS_SIZE, evt.clientY - half));

      const bgX = -((x * zoomState.ratioX) - half);
      const bgY = -((y * zoomState.ratioY) - half);

      $lens
        .css({
          left: `${lensLeft}px`,
          top: `${lensTop}px`,
          backgroundPosition: `${bgX}px ${bgY}px`
        })
        .show();
    };

    $productImage.on("mousemove", move);
    $productImage.on("mouseleave", hideZoomLens);
    $productImage.on("mousedown", (e) => {
      if (e.button !== 0) return;
      zoomState.pressed = true;
      triggerVibration();
      move(e);
    });
    $productImage.on("mouseup", () => {
      zoomState.pressed = false;
      hideZoomLens();
    });

    // Touch support: press-and-hold to zoom
    $productImage.on("touchstart", (e) => {
      zoomState.pressed = true;
      triggerVibration();
      move(e);
    });
    $productImage.on("touchmove", move);
    $productImage.on("touchend touchcancel", () => {
      zoomState.pressed = false;
      hideZoomLens();
    });
  }

  // Полностью убираем превью-галерею из DOM (на случай старого кэша)
  $(document).on("DOMContentLoaded", () => {
    $(".cfg-gallery").remove();
  });

  // Перестановка характеристик под ценой на мобильных
  const $specs = $el(".specs");
  const specsOriginalParent = $specs.parent();
  const specsOriginalNext = $specs.next();
  const $productImage = $el(".product-image");
  const $mainImg = $el(".cfg-main-image");
  let imageLoadId = 0;
  const zoomState = { ratioX: 1, ratioY: 1, enabled: false, pressed: false };
  const ZOOM_LENS_SIZE = 160;

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

  // Управление положением/масштабом фото в зависимости от наличия каркаса
  function updateImageLayout() {
    if (!$productImage.length) return;
    const frameValue = ($el(".cfg-select-frame").val() || "").toLowerCase();
    const hasFrame = !!frameValue && frameValue !== "нет";

    $productImage.toggleClass("with-frame", hasFrame);
    $productImage.toggleClass("without-frame", !hasFrame);
  }

  // Установка картинки с отображением спиннера на время загрузки
  function setMainImageSrc(src) {
    if (!$mainImg.length || !$productImage.length) return;
    imageLoadId += 1;
    const localId = imageLoadId;

    // Если src пустой — просто очистим и уберем спиннер
    if (!src) {
      $mainImg.attr("src", "");
      $productImage.removeClass("is-loading");
      hideZoomLens();
      return;
    }

    $productImage.addClass("is-loading");

    // Снимаем старые обработчики, чтобы избежать гонок
    $mainImg.off("load.cfg error.cfg");

    $mainImg.on("load.cfg error.cfg", () => {
      // Убеждаемся, что это актуальная загрузка
      if (localId === imageLoadId) {
        $productImage.removeClass("is-loading");
        updateZoomMetrics();
        updateZoomImage(src);
      }
    });

    // Триггерим загрузку
    $mainImg.attr("src", src);
  }

  function fillSelects() {
    const m = state.machines;
    populateSelect($el(".cfg-select-machine"), m.map((x) => x.model || x.name), "Выберите кофемашину", false);
    populateSelect($el(".cfg-select-frame"), m.map((x) => x.frame), "Выберите каркас");

    // Селект цвета каркаса: английские ключи, без placeholder (черный по умолчанию)
    populateColorSelect($el(".cfg-select-frame-color"), FRAME_COLORS, null);

    populateSelect($el(".cfg-select-fridge"), m.map((x) => x.refrigerator), "Выберите холодильник");
    populateSelect($el(".cfg-select-terminal"), m.map((x) => x.terminal), "Выберите терминал");

    // Селект цвета вставки: английские ключи, без placeholder (синий по умолчанию)
    populateColorSelect($el(".cfg-select-insert-color"), INSERT_COLORS, null);

    ensureMachineSelection();
    ensureFridgeSelection();
    updateFrameColorState();
    updateInsertColorState();
  }

  function updateFrameColorState() {
    const frameValue = $el(".cfg-select-frame").val();
    const $frameColor = $el(".cfg-select-frame-color");
    const $frameColorLabel = $frameColor.closest('.config-item').find('.config-label');

    // Если каркас не выбран или "Нет" - отключаем выбор цвета
    if (!frameValue || frameValue === "" || frameValue.toLowerCase() === "нет") {
      $frameColor.prop("disabled", true);
      $frameColorLabel.addClass('disabled-label');
      $frameColor.val("");
    } else {
      $frameColor.prop("disabled", false);
      $frameColorLabel.removeClass('disabled-label');

      // Автоматически выбираем черный цвет, если не выбран другой
      if (!$frameColor.val()) {
        $frameColor.val("black");  // Английский ключ
      }
    }
  }

  function hasDesignImageForSelection(v, frameColor, insertColor) {
    if (!v.design_images || !frameColor || !insertColor) return false;
    const found = getDesignConfig(v, frameColor, insertColor);
    return !!(found && found.config && (found.config.main_image || found.config.main_image_path));
  }

  function hasAnyDesignForFrame(v, frameColor) {
    if (!v.design_images || !frameColor) return false;
    const res = findDesignImageForFrame(v.design_images, frameColor);
    return !!(res && res.config && (res.config.main_image || res.config.main_image_path));
  }

  function variantScore(v, frameColor, insertColor) {
    // Приоритет: точная пара с картинкой > есть картинка для каркаса > есть основное изображение > нет картинок
    if (hasDesignImageForSelection(v, frameColor, insertColor)) return 3;
    if (hasAnyDesignForFrame(v, frameColor)) return 2;
    if (v.main_image || (v.gallery_files && v.gallery_files.length)) return 1;
    return 0;
  }

  // Первая попытка — точное совпадение по всем селектам + картинка для выбранных цветов
  // Вторая — совпадение по селектам + картинка для выбранного каркаса
  // Третья — совпадение по селектам (как было)
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

      // ИСПРАВЛЕНИЕ: Если выбран цвет каркаса, проверяем что он есть в design_images (с нормализацией ключей)
      // и что для этого цвета реально есть хотя бы одна картинка (не пустой объект).
      if (fcv && v.design_images) {
        const target = normFcv;
        const hasColorWithImage = Object.entries(v.design_images).some(([k, val]) => {
          if (normalizeColorKey(k) !== target) return false;
          if (!val || typeof val !== "object") return false;
          return Object.values(val).some(cfg => cfg && (cfg.main_image || cfg.main_image_path));
        });
        if (!hasColorWithImage) return false;
      } else if (fcv && !v.design_images) {
        return false;
      }
      // Если у варианта явно указан frame_color — сравниваем его с выбором пользователя
      if (fcv && v.frame_color && normalizeColorKey(v.frame_color) !== normFcv) return false;

      if (rv && normVal(v.refrigerator) !== normVal(rv)) return false;
      if (tv && normVal(v.terminal) !== normVal(tv)) return false;
      return true;
    };

    // Базовые совпадения (строгое сравнение frame)
    const matchesAll = state.machines.filter((v) => !excludedVariants.has(v.id) && baseFilter(v));

    const exactWithImage = matchesAll.filter((v) => hasDesignImageForSelection(v, normFcv, normInsert));
    const exactWithFrameImage = matchesAll.filter((v) => hasAnyDesignForFrame(v, normFcv));

    // Диагностика: какие варианты прошли фильтр
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
        design_images: frameEntries
      };
    };

    console.log("🔎 Candidate variants", {
      selection: { mv, fv, fcv, normFcv, normInsert, rv, tv },
      matchesAll: matchesAll.map(describe),
      withPairImage: exactWithImage.map(describe),
      withFrameImage: exactWithFrameImage.map(describe),
    });

    // 1) строго по селектам + есть картинка для выбранных цветов
    if (exactWithImage.length) return exactWithImage[0];

    // 2) строго по селектам + есть картинка для выбранного цвета каркаса
    if (exactWithFrameImage.length) return exactWithFrameImage[0];

    // 3) как было: все совпадения по селектам, отсортированные по score
    let cands = matchesAll;

    if (!cands.length) return allowEmpty ? null : (state.machines[0] || null);

    // Отдаем предпочтение варианту, у которого реально есть картинка под выбранные цвета (или хотя бы под каркас)
    cands = cands
      .map((v) => ({ v, score: variantScore(v, normFcv, normInsert) }))
      .sort((a, b) => b.score - a.score);

    return cands[0]?.v || cands[0];
  }

  function renderVariant(v, syncSelects = false) {
    if (!v) {
      state.current = null;
      setText($el(".cfg-price-right"), "—");
      setText($el(".cfg-price-left"), "—");
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

      // ИСПРАВЛЕНИЕ: Маппинг русских значений frame_color из БД на английские ключи для селекта
      const frameColorMapping = {
        "белый": "white",
        "чёрный": "black",
        "черный": "black"  // и с е и с ё
      };
      const mappedFrameColor = frameColorMapping[v.frame_color] || v.frame_color;
      setSelVal(".cfg-select-frame-color", mappedFrameColor || "");

      setSelVal(".cfg-select-fridge", v.refrigerator || "");
      setSelVal(".cfg-select-terminal", v.terminal || "");
    }

    updateFrameColorState();
    updateInsertColorState();
    updateImageLayout();
    updateTerminalState();

    // Проверяем, нужно ли использовать design_images
    let mainSrc = "";
    let galleryFolder = v.gallery_folder;
    let usingDesignImages = false;
    const frameValue = ($el(".cfg-select-frame").val() || "").toLowerCase();
    let frameColor = normalizeColorKey($el(".cfg-select-frame-color").val());
    let insertColor = normalizeColorKey($el(".cfg-select-insert-color").val());

    console.log("🔍 renderVariant Debug:", {
      machineId: v.id,
      machineName: v.name,
      frameValue,
      frameColor,
      insertColor,
      frameColorRawSelect: $el(".cfg-select-frame-color").val(),
      insertColorRawSelect: $el(".cfg-select-insert-color").val(),
      frameColorFromVariant: v.frame_color,
      hasDesignImages: !!v.design_images,
      designImagesKeys: v.design_images ? Object.keys(v.design_images) : [],
      designImagesFullStructure: v.design_images,
      mainImage: v.main_image
    });

    // Детальная проверка условия
    console.log("🔍 Condition check:", {
      "frameValue": frameValue,
      "frameValue truthy": !!frameValue,
      "frameValue !== 'нет'": frameValue !== "нет",
      "frameValue !== 'no'": frameValue !== "no",
      "frameColor": frameColor,
      "frameColor truthy": !!frameColor,
      "insertColor": insertColor,
      "insertColor truthy": !!insertColor,
      "v.design_images exists": !!v.design_images,
      "FULL CONDITION RESULT": !!(frameValue && frameValue !== "нет" && frameValue !== "no" && frameColor && insertColor && v.design_images)
    });

      // Если выбраны цвета и есть design_images, используем их
      if (frameValue && frameValue !== "нет" && frameValue !== "no" &&
          frameColor && insertColor && v.design_images) {

        // Нормализованный поиск картинки по выбранным цветам
        const designLookup = getDesignConfig(v, frameColor, insertColor);
        let designConfig = designLookup?.config;
        if (designLookup) {
          frameColor = designLookup.frameColor;
          insertColor = designLookup.insertColor;
        }

        console.log("✓ Checking design_images:", {
          frameColor,
          insertColor,
          frameColorLabel: COLOR_LABELS[frameColor],
          insertColorLabel: COLOR_LABELS[insertColor],
          availableFrameColors: Object.keys(v.design_images),
          designConfig: designConfig,
          foundConfig: !!designConfig,
          variantId: v.id
        });

        // Fallback: если для выбранной пары нет картинки, пробуем найти любую вставку в этом же цвете каркаса
        if (!designConfig) {
          const fallbackDesign = findDesignImageForFrame(v.design_images, frameColor);
          if (fallbackDesign) {
            designConfig = fallbackDesign.config;
            console.log("ℹ️ Falling back to available design_images combo:", {
              fallbackFrameColor: fallbackDesign.frameColor,
              fallbackInsertColor: fallbackDesign.insertColor
            });
          }
        }

        // Если есть ключ каркаса, но в нём нет картинок — исключаем этот variant и пробуем следующий
        if (!designConfig) {
          const hasSelectedColorKey = Object.keys(v.design_images || {}).some(k => normalizeColorKey(k) === frameColor);
          if (hasSelectedColorKey) {
            excludedVariants.add(v.id);
            console.warn("⛔ Skipping variant with empty design_images for selected frame color", { variantId: v.id, frameColor });
            const alt = findVariant(true);
            if (alt && alt.id !== v.id) {
              renderVariant(alt, true);
              return;
            }
          }
        }

        if (designConfig) {
          mainSrc = normSrc(designConfig.main_image || designConfig.main_image_path || "");
          usingDesignImages = true;
          console.log("✓ Using design_images URL:", {
            rawMainImage: designConfig.main_image,
          rawMainImagePath: designConfig.main_image_path,
          normalizedSrc: mainSrc
        });
        if (designConfig.gallery_folder) {
          galleryFolder = designConfig.gallery_folder;
        }
      } else {
        console.warn("⚠️  No design config found for", frameColor, "/", insertColor, "variant id:", v.id);
      }
    }

    // Если не нашли в design_images, используем основное изображение
    if (!mainSrc) {
      mainSrc = normSrc(v.main_image || (v.gallery_files && v.gallery_files[0]) || "");
      console.log("📷 Using fallback main_image:", {
        rawMainImage: v.main_image,
        normalizedSrc: mainSrc
      });
    }

    const $mainImg = $el(".cfg-main-image");
    if ($mainImg.length) {
      setMainImageSrc(mainSrc || "");
      // сразу обновим фон лупы, чтобы не мигал старый src
      if (mainSrc) {
        updateZoomImage(mainSrc);
      } else {
        hideZoomLens();
      }
    }

    const vWithGallery = { ...v, gallery_folder: galleryFolder };

    ensureImageNav();

    // Для design_images не вызываем updateMainImage, т.к. это одиночное изображение,
    // а не галерея. updateMainImage может перезаписать src пустым значением.
    if (!usingDesignImages) {
      updateMainImage(vWithGallery);
    } else {
      // Скрываем навигацию по галерее для design_images
      $(".cfg-image-nav").hide();
    }

    preloadVariantImages(v);
    setText($el(".cfg-price-right"), fmtPrice(v.price));

    const $priceLeft = $el(".cfg-price-left");
    const ozonBtn = $el(".cfg-btn-ozon");
    $priceLeft.empty();
    if (ozonBtn.length) {
      if (v.ozon_link) {
        ozonBtn.removeClass("disabled").attr("href", v.ozon_link).text("Купить на OZON");
      } else {
        ozonBtn.addClass("disabled").attr("href", "#").text("Нет на OZON");
      }
    }

    const specM = state.specs["coffee_machine"]?.[v.model || v.name] || null;
    const specF = state.specs["frame"]?.[v.frame] || null;
    const specR = state.specs["refrigerator"]?.[v.refrigerator] || null;
    const selectedTerminal = $el(".cfg-select-terminal").val();
    const specT = selectedTerminal
      ? state.specs["terminal"]?.[selectedTerminal] || state.specs["terminal"]?.[v.terminal] || null
      : null;

    renderSpecs($el(".cfg-spec-machine"), specM);
    renderSpecs($el(".cfg-spec-frame"), specF);
    renderSpecs($el(".cfg-spec-fridge"), specR);
    renderSpecs($el(".cfg-spec-terminal"), specT);

    saveSelection();
  }

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

    const payload = {
      name: name,
      phone: phone,
      telegram: telegram || "",
      email: email || "",
      selection: v ? {
        id: v.id,
        machine: v.model || v.name,
        frame: v.frame,
        frame_color: v.frame_color,
        refrigerator: v.refrigerator,
        terminal: v.terminal,
        price: v.price,
        ozon_link: v.ozon_link,
        gallery_folder: v.gallery_folder,
      } : null,
    };

    return $.ajax({
      url: LEAD_ENDPOINT,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify(payload),
    });
  }

  function bindEvents() {
    $(".cfg-select-machine, .cfg-select-frame, .cfg-select-frame-color, .cfg-select-fridge, .cfg-select-terminal, .cfg-select-insert-color").on(
      "change",
      () => {
        ensureMachineSelection();
        ensureFridgeSelection();
        updateFrameColorState();
        updateInsertColorState();
        updateImageLayout();
        renderVariant(findVariant(true));
      }
    );

    $(window).on("resize", repositionSpecs);

    $el(".cfg-btn-quote").on("click", (e) => {
      e.preventDefault();
      openModal();
    });

    $(".cfg-modal-close, .cfg-modal-overlay").on("click", (e) => {
      e.preventDefault();
      closeModal();
    });

    $("#cfg-lead-name, #cfg-lead-phone, #cfg-lead-consent").on("input change", validateForm);

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
          $message.addClass("success").text("Заявка успешно отправлена!").show();
          setTimeout(() => {
            closeModal();
          }, 2000);
        })
        .fail(() => {
          $message.addClass("error").text("Не удалось отправить заявку. Попробуйте ещё раз.").show();
          $submitBtn.prop("disabled", false).text("Отправить");
        });
    });
  }

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
          state.machines.slice(0, 5).forEach(machine => {
            preloadVariantImages(machine);
          });
        }, 500);
        hideInitialLoader();
      })
      .fail(() => console.error("Не удалось загрузить конфигуратор"))
      .always(() => hideInitialLoader());
  });
})(jQuery);
