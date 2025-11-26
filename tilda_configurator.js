(function ($) {
  // Настройте базовый URL бэкенда (домен + порт)
  const BACKEND_BASE = "https://93-170-123-229.nip.io"; // замените на свой
  const API_BASE = `${BACKEND_BASE}/api`;
  const LEAD_ENDPOINT = `${API_BASE}/lead`;

  // ВАЖНО: Укажите recID вашего блока с конфигуратором (например, '712345678')
  const CONFIGURATOR_REC_ID = null; // замените на ID вашего блока

  // Если нужно инжектить модалку в конкретный ZeroBlock, укажите его recID (например, '123456'); иначе оставьте null
  const MODAL_REC_ID = null;

  // State
  const state = { machines: [], specs: {}, current: null };
  const skipValues = new Set(["да", "нет", "-", "none", "", null, undefined]);
  const INSERT_COLORS = ["жёлтый", "зелёный", "красный", "серый", "синий", "фиолетовый"];

  // Helpers - поиск элементов внутри блока конфигуратора
  const getScope = () => CONFIGURATOR_REC_ID ? `#rec${CONFIGURATOR_REC_ID} ` : '';
  const $el = (cls) => $(`${getScope()}${cls}`).first();
  const $all = (cls) => $(`${getScope()}${cls}`);
  const setText = (jq, txt) => jq.length && jq.text(txt ?? "—");
  const fmtPrice = (v) => (v || v === 0 ? Number(v).toLocaleString("ru-RU") + " ₽" : "—");

  function renderSpecs($block, spec) {
    if (!$block.length) return;
    const lines = spec?.specs || [];
    if (!lines.length) {
      $block.html('<div class="text-muted small">—</div>');
      return;
    }
    $block.html(
      `<div class="fw-semibold">${spec.name}</div><div class="text-muted small" style="white-space:pre-line;">${lines.join(
        "\n"
      )}</div>`
    );
  }

  function populateSelect($sel, values, placeholder) {
    if (!$sel.length) return;
    const uniq = Array.from(new Set(values.filter((v) => v && !skipValues.has(String(v).toLowerCase()))));
    const opts = placeholder ? [`<option value="">${placeholder}</option>`] : [];
    uniq.forEach((v) => opts.push(`<option value="${v}">${v}</option>`));
    $sel.html(opts.join(""));
  }

  function loadData() {
    const mReq = $.getJSON(`${API_BASE}/coffee-machines?include_gallery=true`);
    const sReq = $.getJSON(`${API_BASE}/specs`);
    return $.when(mReq, sReq).then(([m], [s]) => {
      state.machines = m || [];
      state.specs = {};
      (s || []).forEach((sp) => {
        if (!state.specs[sp.category]) state.specs[sp.category] = {};
        state.specs[sp.category][sp.name] = sp;
      });
    });
  }

  function fillSelects() {
    const m = state.machines;
    populateSelect($el(".cfg-select-machine"), m.map((x) => x.model || x.name), "Кофемашина");
    populateSelect($el(".cfg-select-frame"), m.map((x) => x.frame), "Каркас");
    populateSelect($el(".cfg-select-frame-color"), m.map((x) => x.frame_color), "Цвет каркаса");
    populateSelect($el(".cfg-select-fridge"), m.map((x) => x.refrigerator), "Холодильник");
    populateSelect($el(".cfg-select-terminal"), m.map((x) => x.terminal), "Терминал");
    populateSelect($el(".cfg-select-insert-color"), INSERT_COLORS, "Цвет вставки");
  }

  function findVariant() {
    const mv = $el(".cfg-select-machine").val();
    const fv = $el(".cfg-select-frame").val();
    const fcv = $el(".cfg-select-frame-color").val();
    const rv = $el(".cfg-select-fridge").val();
    const tv = $el(".cfg-select-terminal").val();
    const cands = state.machines.filter((v) => {
      if (mv && (v.model || v.name) !== mv) return false;
      if (fv && v.frame !== fv) return false;
      if (fcv && v.frame_color !== fcv) return false;
      if (rv && v.refrigerator !== rv) return false;
      if (tv && v.terminal !== tv) return false;
      return true;
    });
    return cands[0] || state.machines[0] || null;
  }

  function getDesignImages(variant, frameColor, insertColor) {
    if (!variant || !variant.design_images || !frameColor || !insertColor) return null;
    return variant.design_images[frameColor]?.[insertColor] || null;
  }

  function renderVariant(v) {
    if (!v) return;
    state.current = v;

    // Получаем выбранные цвета
    const frameColor = $el(".cfg-select-frame-color").val();
    const insertColor = $el(".cfg-select-insert-color").val();

    // Получаем изображения для комбинации цветов, если выбраны
    let mainSrc = v.main_image;
    let galleryFiles = v.gallery_files || [];

    if (frameColor && insertColor) {
      const designImages = getDesignImages(v, frameColor, insertColor);
      if (designImages) {
        // Если есть специальные изображения для этой комбинации, используем их
        if (designImages.main_image_path || designImages.main_image) {
          mainSrc = designImages.main_image_path || designImages.main_image;
        }
        // Для галереи можно было бы загрузить файлы из gallery_folder,
        // но это требует дополнительного API запроса
      }
    }

    if (!mainSrc && galleryFiles.length > 0) {
      mainSrc = galleryFiles[0];
    }

    // Принудительно устанавливаем src (даже если пусто)
    const $mainImg = $el(".cfg-main-image");
    if ($mainImg.length) {
      $mainImg.attr("src", mainSrc || "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7");
    }

    const $g = $el(".cfg-gallery");
    if ($g.length) {
      $g.empty();
      const imgs = galleryFiles ? [...galleryFiles] : [];
      if (mainSrc) imgs.unshift(mainSrc);
      imgs.forEach((src) => {
        const img = $(
          `<img src="${src}" class="cfg-thumb" style="max-height:80px; margin-right:8px; cursor:pointer;">`
        );
        img.on("click", () => $el(".cfg-main-image").attr("src", src));
        $g.append(img);
      });
    }

    setText($el(".cfg-price-right"), fmtPrice(v.price));
    const ozonBtn = $el(".cfg-btn-ozon");
    const $priceLeft = $el(".cfg-price-left");
    $priceLeft.empty();
    if (ozonBtn.length) {
      if (v.ozon_link) {
        ozonBtn.prop("disabled", false).attr("href", v.ozon_link).text("Купить на OZON");
      } else {
        ozonBtn.prop("disabled", true).attr("href", "#").text("Нет на OZON");
      }
    }


    const specM = state.specs["coffee_machine"]?.[v.model || v.name] || null;
    const specF = state.specs["frame"]?.[v.frame] || null;
    const specR = state.specs["refrigerator"]?.[v.refrigerator] || null;
    const specT = state.specs["terminal"]?.[v.terminal] || null;
    renderSpecs($el(".cfg-spec-machine"), specM);
    renderSpecs($el(".cfg-spec-frame"), specF);
    renderSpecs($el(".cfg-spec-fridge"), specR);
    renderSpecs($el(".cfg-spec-terminal"), specT);
  }

  function openModal() {
    const m = $all(".cfg-modal");
    if (m.length) m.addClass("is-open");
  }
  function closeModal() {
    $all(".cfg-modal").removeClass("is-open");
  }

  function sendLead() {
    const v = state.current;
    const payload = {
      phone: $el(".cfg-lead-phone").val(),
      telegram: $el(".cfg-lead-tg").val(),
      selection: v
        ? {
            id: v.id,
            machine: v.model || v.name,
            frame: v.frame,
            frame_color: v.frame_color,
            refrigerator: v.refrigerator,
            terminal: v.terminal,
            price: v.price,
            ozon_link: v.ozon_link,
            gallery_folder: v.gallery_folder,
          }
        : null,
    };
    return $.ajax({
      url: LEAD_ENDPOINT,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify(payload),
    });
  }

  function bindEvents() {
    $all(".cfg-select-machine, .cfg-select-frame, .cfg-select-frame-color, .cfg-select-fridge, .cfg-select-terminal, .cfg-select-insert-color").on(
      "change",
      () => renderVariant(findVariant())
    );

    $el(".cfg-btn-quote").on("click", (e) => {
      e.preventDefault();
      openModal();
    });
    $el(".cfg-modal-close").on("click", (e) => {
      e.preventDefault();
      closeModal();
    });
    $el(".cfg-lead-submit").on("click", (e) => {
      e.preventDefault();
      sendLead()
        .done(() => {
          alert("Заявка отправлена");
          closeModal();
        })
        .fail(() => alert("Не удалось отправить заявку"));
    });
  }

  $(document).ready(function () {
    // Очищаем битые src у всех изображений конфигуратора
    const scope = getScope();
    $(`${scope}img[src*="{src}"], ${scope}img[src*="\${src}"]`).attr("src", "");

    if (MODAL_REC_ID) {
      const target = document.querySelector(`#rec${MODAL_REC_ID} .t396__artboard`);
      if (target) {
        target.insertAdjacentHTML(
          "beforeend",
          `<div class="cfg-modal">
              <div class="cfg-modal-box">
                <a href="#popup-close" class="cfg-modal-close" style="float:right; text-decoration:none;">×</a>
                <h3>Запросить счёт</h3>
                <div class="mb-2">
                  <label>Телефон</label>
                  <input type="tel" class="cfg-lead-phone" />
                </div>
                <div class="mb-2">
                  <label>Telegram (опц.)</label>
                  <input type="text" class="cfg-lead-tg" />
                </div>
                <button class="cfg-lead-submit">Отправить</button>
              </div>
            </div>`
        );
        const style = document.createElement("style");
        style.textContent = `
          .cfg-modal {display:none; position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,.5); align-items:center; justify-content:center;}
          .cfg-modal.is-open {display:flex;}
          .cfg-modal-box {background:#fff; padding:20px; border-radius:8px; max-width:400px; width:100%;}
        `;
        document.head.appendChild(style);
      }
    }

    loadData()
      .then(() => {
        fillSelects();

        // Установить значения по умолчанию для цветов
        const frameColorSelect = $el(".cfg-select-frame-color");
        const insertColorSelect = $el(".cfg-select-insert-color");

        // Устанавливаем чёрный корпус и синий цвет вставки по умолчанию
        if (frameColorSelect.length && frameColorSelect.find('option[value="чёрный"]').length) {
          frameColorSelect.val("чёрный");
        } else if (frameColorSelect.length && frameColorSelect.find('option[value="Чёрный"]').length) {
          frameColorSelect.val("Чёрный");
        }

        if (insertColorSelect.length) {
          insertColorSelect.val("синий");
        }

        renderVariant(findVariant());
        bindEvents();
      })
      .fail(() => console.error("Не удалось загрузить конфигуратор"));
  });
})(jQuery);

