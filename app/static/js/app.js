document.addEventListener("DOMContentLoaded", () => {
    const modalEl = document.getElementById("machineModal");
    const modal = modalEl ? new bootstrap.Modal(modalEl) : null;
    const form = document.getElementById("machine-form");
    const addBtn = document.getElementById("add-machine-btn");
    const selectAll = document.getElementById("select-all");
    const bulkDeleteBtn = document.getElementById("bulk-delete-btn");
    // Seafile picker elements
    const seafileModalEl = document.getElementById("seafileModal");
    const seafileModal = seafileModalEl ? new bootstrap.Modal(seafileModalEl) : null;
    const seafileList = document.getElementById("seafile-list");
    const seafileStatus = document.getElementById("seafile-status");
    const seafileBreadcrumb = document.getElementById("seafile-breadcrumb");
    const seafileUpBtn = document.getElementById("seafile-up-btn");
    const seafileSelectFolderBtn = document.getElementById("seafile-select-folder-btn");
    const seafileSearchInput = document.getElementById("seafile-search");
    const hasSeafile = !!(seafileModalEl && seafileList && seafileStatus && seafileBreadcrumb);
    let seafileMode = "file"; // "file" | "folder"
    let seafileTargetInput = null;
    let seafilePath = "/";
    function rememberPath(path) {
        try {
            localStorage.setItem("seafile_last_path", path);
        } catch (e) {
            /* ignore */
        }
    }
    function readRememberedPath() {
        try {
            return localStorage.getItem("seafile_last_path") || "/";
        } catch (e) {
            return "/";
        }
    }
    function renderBreadcrumb(path) {
        if (!hasSeafile) return;
        const parts = path.split("/").filter(Boolean);
        let acc = "";
        const links = parts.map((p) => {
            acc += `/${p}`;
            return `<a href="#" data-path="${acc}">${p}</a>`;
        });
        seafileBreadcrumb.innerHTML = `/${links.join("/")}`;
        seafileBreadcrumb.querySelectorAll("a").forEach((a) => {
            a.addEventListener("click", (e) => {
                e.preventDefault();
                loadSeafile(a.dataset.path);
            });
        });
    }
    async function loadSeafile(path) {
        if (!hasSeafile) return;
        seafileStatus.textContent = "Загрузка...";
        seafileList.innerHTML = "";
        try {
            const resp = await fetch(`/admin/seafile-browser?path=${encodeURIComponent(path)}`);
            if (!resp.ok) throw new Error(await resp.text());
            const data = await resp.json();
            seafilePath = data.path || "/";
            rememberPath(seafilePath);
            renderBreadcrumb(seafilePath);
            const frag = document.createDocumentFragment();
            const dirs = Array.isArray(data.items) ? data.items.filter((i) => i.type === "dir") : [];
            const files = Array.isArray(data.items) ? data.items.filter((i) => i.type === "file") : [];
            dirs.forEach((d) => {
                const el = document.createElement("button");
                el.type = "button";
                el.className = "list-group-item list-group-item-action d-flex justify-content-between align-items-center";
                el.dataset.path = d.path || d.name;
                el.innerHTML = `<span>[DIR] ${d.name}</span><span class="text-muted small">Папка</span>`;
                el.addEventListener("click", () => {
                    const base = seafilePath.replace(/\/$/, "");
                    const targetPath = d.path || `${base}/${d.name}`;
                    loadSeafile(targetPath);
                });
                frag.appendChild(el);
            });
            files.forEach((f) => {
                const el = document.createElement("button");
                el.type = "button";
                el.className = "list-group-item list-group-item-action d-flex justify-content-between align-items-center";
                el.dataset.path = f.path || f.name;
                el.innerHTML = `<span>[FILE] ${f.name}</span><span class="text-muted small">${f.size || ""}</span>`;
                el.addEventListener("click", () => selectSeafileFile(f));
                frag.appendChild(el);
            });
            seafileList.innerHTML = "";
            seafileList.appendChild(frag);
            seafileStatus.textContent = `${dirs.length} папок, ${files.length} файлов`;
            // фильтр по поиску
            const q = (seafileSearchInput?.value || "").trim().toLowerCase();
            if (q) {
                filterSeafileList(q);
            }
        } catch (err) {
            console.error(err);
            seafileStatus.textContent = "Ошибка загрузки";
        }
    }
    function filterSeafileList(query) {
        const q = query.toLowerCase();
        seafileList.querySelectorAll(".list-group-item").forEach((el) => {
            const name = (el.textContent || "").toLowerCase();
            el.style.display = name.includes(q) ? "" : "none";
        });
    }
    async function selectSeafileFile(file) {
        if (!hasSeafile || !seafileTargetInput) return;
        const filePath = file.path || `${seafilePath.replace(/\/$/, "")}/${file.name}`;

        // Design images field
        if (seafileTargetInput.designKey) {
            const key = seafileTargetInput.designKey;
            const field = seafileTargetInput.field;
            if (seafileMode === "file") {
                try {
                    const resp = await fetch(`/admin/seafile-file?path=${encodeURIComponent(filePath)}`);
                    if (!resp.ok) throw new Error(await resp.text());
                    const data = await resp.json();
                    const input = form?.querySelector(`[data-design-field="${key}-${field}"]`);
                    if (input) input.value = data.path || filePath;
                    seafileModal?.hide();
                } catch (err) {
                    alert("Не удалось получить ссылку на файл из Seafile");
                }
            }
            return;
        }

        // Regular field
        if (seafileMode !== "file") return;
        try {
            const resp = await fetch(`/admin/seafile-file?path=${encodeURIComponent(filePath)}`);
            if (!resp.ok) throw new Error(await resp.text());
            const data = await resp.json();
            seafileTargetInput.value = data.link;
            const pathInput = form?.querySelector('[name="main_image_path"]');
            if (pathInput) {
                pathInput.value = data.path || filePath;
            }
            seafileModal?.hide();
        } catch (err) {
            alert("Не удалось получить ссылку на файл из Seafile");
        }
    }
    function openSeafile(mode, targetName) {
        if (!hasSeafile) {
            alert("Seafile UI недоступен на этой странице");
            return;
        }
        seafileMode = mode;
        seafileTargetInput = form?.querySelector(`[name="${targetName}"]`);
        if (!seafileTargetInput) return;
        seafileModal?.show();
        const startPath = readRememberedPath();
        loadSeafile(startPath || "/");
    }
    if (hasSeafile) {
        seafileUpBtn?.addEventListener("click", () => {
            if (seafilePath === "/") return;
            const parts = seafilePath.split("/").filter(Boolean);
            parts.pop();
            const newPath = "/" + parts.join("/");
            loadSeafile(newPath || "/");
        });
        seafileSelectFolderBtn?.addEventListener("click", () => {
            if (seafileMode !== "folder" || !seafileTargetInput) return;
            // Design images field
            if (seafileTargetInput.designKey) {
                const key = seafileTargetInput.designKey;
                const field = seafileTargetInput.field;
                const input = form?.querySelector(`[data-design-field="${key}-${field}"]`);
                if (input) input.value = seafilePath;
                seafileModal?.hide();
                return;
            }
            // Regular field
            seafileTargetInput.value = seafilePath;
            seafileModal?.hide();
        });
        seafileSearchInput?.addEventListener("input", (e) => {
            filterSeafileList(e.target.value);
        });
        document.querySelectorAll(".btn-seafile").forEach((btn) => {
            btn.addEventListener("click", () => {
                openSeafile(btn.dataset.mode, btn.dataset.target);
            });
        });
    }
    document.querySelectorAll(".btn-clear-field").forEach((btn) => {
        btn.addEventListener("click", () => {
            const target = btn.dataset.target;
            if (!target) return;
            const input = form?.querySelector(`[name="${target}"]`);
            const clearFlag = btn.dataset.clearFlag ? form?.querySelector(`[name="${btn.dataset.clearFlag}"]`) : null;
            if (input) {
                input.value = "";
                const evt = new Event("input", { bubbles: true });
                input.dispatchEvent(evt);
            }
            // Дополнительно чистим связанный path и флаг, если есть
            if (target === "main_image") {
                const pathInput = form?.querySelector('[name="main_image_path"]');
                const clearPath = form?.querySelector('[name="clear_main_image_path"]');
                if (pathInput) pathInput.value = "";
                if (clearPath) clearPath.value = "1";
            }
            if (clearFlag) {
                clearFlag.value = "1";
            }
        });
    });
    // Design images state
    const FRAME_COLORS = ["white", "black"];
    const INSERT_COLORS = ["yellow", "green", "red", "gray", "blue", "purple"];

    // Маппинг английских ключей на русские названия для отображения
    const COLOR_NAMES = {
        "white": "Белый",
        "black": "Чёрный",
        "yellow": "Жёлтый",
        "green": "Зелёный",
        "red": "Красный",
        "gray": "Серый",
        "blue": "Синий",
        "purple": "Фиолетовый"
    };

    let designImagesData = {};

    function initDesignImagesUI() {
        const whiteContainer = document.getElementById("white-inserts");
        const blackContainer = document.getElementById("black-inserts");
        if (!whiteContainer || !blackContainer) return;

        function createInsertFields(frameColor, insertColor) {
            const key = `${frameColor}-${insertColor}`;
            const div = document.createElement("div");
            div.className = "col-12";
            div.innerHTML = `
                <div class="card mb-2">
                    <div class="card-body">
                        <h6 class="card-title">${COLOR_NAMES[insertColor]}</h6>
                        <div class="mb-2">
                            <label class="form-label small">Главное фото</label>
                            <div class="input-group input-group-sm">
                                <input type="text" class="form-control" data-design-field="${key}-main_image" placeholder="URL или путь">
                                <button type="button" class="btn btn-outline-secondary btn-design-seafile"
                                    data-frame="${frameColor}" data-insert="${insertColor}" data-field="main_image">
                                    Seafile
                                </button>
                            </div>
                        </div>
                        <div class="mb-0">
                            <label class="form-label small">Папка галереи</label>
                            <div class="input-group input-group-sm">
                                <input type="text" class="form-control" data-design-field="${key}-gallery_folder" placeholder="Путь к папке">
                                <button type="button" class="btn btn-outline-secondary btn-design-seafile"
                                    data-frame="${frameColor}" data-insert="${insertColor}" data-field="gallery_folder">
                                    Seafile
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            return div;
        }

        whiteContainer.innerHTML = "";
        blackContainer.innerHTML = "";

        INSERT_COLORS.forEach((insertColor) => {
            whiteContainer.appendChild(createInsertFields("white", insertColor));
            blackContainer.appendChild(createInsertFields("black", insertColor));
        });

        // Bind Seafile buttons
        document.querySelectorAll(".btn-design-seafile").forEach((btn) => {
            btn.addEventListener("click", () => {
                const frame = btn.dataset.frame;
                const insert = btn.dataset.insert;
                const field = btn.dataset.field;
                const key = `${frame}-${insert}`;
                seafileTargetInput = { designKey: key, field: field };
                seafileMode = field === "gallery_folder" ? "folder" : "file";
                seafileModal?.show();
                const startPath = readRememberedPath();
                loadSeafile(startPath || "/");
            });
        });
    }

    function loadDesignImages(data) {
        designImagesData = data || {};
        FRAME_COLORS.forEach((frame) => {
            INSERT_COLORS.forEach((insert) => {
                const key = `${frame}-${insert}`;
                const config = designImagesData[frame]?.[insert] || {};
                const mainInput = form?.querySelector(`[data-design-field="${key}-main_image"]`);
                const galleryInput = form?.querySelector(`[data-design-field="${key}-gallery_folder"]`);
                if (mainInput) mainInput.value = config.main_image_path || config.main_image || "";
                if (galleryInput) galleryInput.value = config.gallery_folder || "";
            });
        });
    }

    function collectDesignImages() {
        const result = {};
        FRAME_COLORS.forEach((frame) => {
            result[frame] = {};
            INSERT_COLORS.forEach((insert) => {
                const key = `${frame}-${insert}`;
                const mainInput = form?.querySelector(`[data-design-field="${key}-main_image"]`);
                const galleryInput = form?.querySelector(`[data-design-field="${key}-gallery_folder"]`);
                const main = mainInput?.value || "";
                const gallery = galleryInput?.value || "";
                if (main || gallery) {
                    result[frame][insert] = {
                        main_image: main,
                        main_image_path: main,
                        gallery_folder: gallery,
                    };
                }
            });
        });
        return result;
    }

    function updateDesignSectionVisibility() {
        if (!form) return;
        const frameValue = (form.querySelector('[name="frame"]')?.value || "").toLowerCase();
        const designSection = document.getElementById("design-images-section");
        const mainImageInput = form.querySelector('[name="main_image"]');
        const mainImagePathInput = form.querySelector('[name="main_image_path"]');
        const galleryFolderInput = form.querySelector('[name="gallery_folder"]');

        // Если каркас = "нет" или пустой, показываем обычные поля
        if (!frameValue || frameValue === "нет" || frameValue === "no") {
            if (designSection) designSection.style.display = "none";
            if (mainImageInput) mainImageInput.disabled = false;
            if (galleryFolderInput) galleryFolderInput.disabled = false;
            // Включаем кнопки Seafile для обычных полей
            document.querySelectorAll('.btn-seafile[data-target="main_image"], .btn-seafile[data-target="gallery_folder"]').forEach(btn => {
                btn.disabled = false;
            });
        } else {
            // Если выбран каркас, показываем секцию дизайна
            if (designSection) designSection.style.display = "block";
            if (mainImageInput) mainImageInput.disabled = true;
            if (galleryFolderInput) galleryFolderInput.disabled = true;
            // Отключаем кнопки Seafile для обычных полей
            document.querySelectorAll('.btn-seafile[data-target="main_image"], .btn-seafile[data-target="gallery_folder"]').forEach(btn => {
                btn.disabled = true;
            });
        }
    }

    function fillForm(data) {
        if (!form) return;
        form.reset();
        form.querySelector("#machine-id").value = data?.id || "";
        const fields = [
            "name",
            "model",
            "frame",
            "frame_color",
            "refrigerator",
            "terminal",
            "price",
            "ozon_link",
            "graphic_link",
            "main_image",
            "main_image_path",
            "gallery_folder",
            "description",
        ];
        fields.forEach((f) => {
            const el = form.querySelector(`[name="${f}"]`);
            if (el) el.value = data?.[f] ?? "";
        });
        loadDesignImages(data?.design_images);
        updateDesignSectionVisibility();
    }
    function showEdit(btn) {
        const row = btn.closest("tr");
        const dataAttr = row?.dataset.machine;
        if (!dataAttr) return;
        const data = JSON.parse(dataAttr);
        fillForm(data);
        modal?.show();
    }
    function showCreate() {
        fillForm({});
        modal?.show();
    }
    async function saveForm(event) {
        event.preventDefault();
        if (!form) return;
        const id = form.querySelector("#machine-id").value;
        const formData = new FormData(form);

        // Collect and add design_images data
        const designData = collectDesignImages();
        formData.set("design_images", JSON.stringify(designData));

        const url = id ? `/admin/machine/${id}` : "/admin/machine";
        try {
            const resp = await fetch(url, { method: "POST", body: formData });
            if (!resp.ok) {
                const msg = await resp.text();
                alert(`Ошибка при сохранении: ${msg}`);
                return;
            }
            if (modalEl) {
                modalEl.addEventListener(
                    "hidden.bs.modal",
                    () => {
                        location.reload();
                    },
                    { once: true }
                );
                modal?.hide();
            } else {
                location.reload();
            }
        } catch (err) {
            alert("Ошибка при отправке формы.");
        }
    }
    async function deleteOne(id) {
        if (!confirm("Удалить запись?")) return;
        const resp = await fetch(`/admin/machine/${id}/delete`, { method: "POST" });
        if (!resp.ok) {
            alert("Ошибка удаления");
            return;
        }
        location.reload();
    }
    async function bulkDelete() {
        const ids = Array.from(document.querySelectorAll(".row-select:checked")).map((el) =>
            parseInt(el.dataset.id, 10)
        );
        if (!ids.length) return;
        if (!confirm(`Удалить выбранные (${ids.length})?`)) return;
        const resp = await fetch("/admin/machines/bulk-delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids }),
        });
        if (!resp.ok) {
            let msg = "Ошибка массового удаления";
            try {
                const text = await resp.text();
                msg += `: ${text}`;
            } catch (e) {
                /* ignore */
            }
            alert(msg);
            return;
        }
        location.reload();
    }
    function syncBulkButtons() {
        const ids = document.querySelectorAll(".row-select:checked");
        if (bulkDeleteBtn) bulkDeleteBtn.disabled = ids.length === 0;
    }
    document.querySelectorAll(".btn-edit").forEach((btn) => {
        btn.addEventListener("click", () => showEdit(btn));
    });
    document.querySelectorAll(".btn-delete").forEach((btn) => {
        btn.addEventListener("click", () => {
            const row = btn.closest("tr");
            const dataAttr = row?.dataset.machine;
            if (!dataAttr) return;
            const data = JSON.parse(dataAttr);
            deleteOne(data.id);
        });
    });
    addBtn?.addEventListener("click", showCreate);
    form?.addEventListener("submit", saveForm);
    document.querySelectorAll(".row-select").forEach((chk) =>
        chk.addEventListener("change", () => {
            syncBulkButtons();
            if (!chk.checked && selectAll) selectAll.checked = false;
        })
    );
    selectAll?.addEventListener("change", () => {
        const checked = selectAll.checked;
        document.querySelectorAll(".row-select").forEach((chk) => {
            chk.checked = checked;
        });
        syncBulkButtons();
    });
    bulkDeleteBtn?.addEventListener("click", bulkDelete);

    // Initialize design images UI
    initDesignImagesUI();

    // Watch for frame field changes to show/hide design section
    const frameInput = form?.querySelector('[name="frame"]');
    if (frameInput) {
        frameInput.addEventListener('change', updateDesignSectionVisibility);
        frameInput.addEventListener('input', updateDesignSectionVisibility);
    }

    // Initial visibility update
    updateDesignSectionVisibility();

    // Колонка ресайз
    const table = document.getElementById("machines-table");
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;
    let resizeColIndex = -1;
    function startResize(e, th) {
        isResizing = true;
        startX = e.clientX;
        resizeColIndex = Array.from(th.parentElement.children).indexOf(th);
        startWidth = th.getBoundingClientRect().width;
        document.addEventListener("mousemove", onResize);
        document.addEventListener("mouseup", stopResize);
        e.preventDefault();
    }
    function onResize(e) {
        if (!isResizing || !table || resizeColIndex < 0) return;
        const delta = e.clientX - startX;
        const newWidth = Math.max(60, startWidth + delta);
        const rows = table.querySelectorAll("tr");
        rows.forEach((row) => {
            const cell = row.children[resizeColIndex];
            if (cell) cell.style.width = `${newWidth}px`;
        });
    }
    function stopResize() {
        isResizing = false;
        resizeColIndex = -1;
        document.removeEventListener("mousemove", onResize);
        document.removeEventListener("mouseup", stopResize);
    }
    if (table) {
        table.querySelectorAll("th").forEach((th) => {
            const handle = th.querySelector(".table-resize-handle");
            handle?.addEventListener("mousedown", (e) => startResize(e, th));
        });
    }
    // Specs page logic
    const specsTable = document.getElementById("specs-table");
    const specModalEl = document.getElementById("specModal");
    const specModal = specModalEl ? new bootstrap.Modal(specModalEl) : null;
    const specForm = document.getElementById("spec-form");
    const addSpecBtn = document.getElementById("add-spec-btn");
    const populateSpecsBtn = document.getElementById("populate-specs-btn");
    const bulkDeleteSpecsBtn = document.getElementById("bulk-delete-specs");
    const selectAllSpecs = document.getElementById("select-all-specs");
    function fillSpecForm(data) {
        if (!specForm) return;
        specForm.reset();
        specForm.querySelector("#spec-id").value = data?.id || "";
        ["category", "name", "specs_text"].forEach((f) => {
            const el = specForm.querySelector(`[name="${f}"]`);
            if (el) el.value = data?.[f] ?? "";
        });
    }
    function showSpecEdit(btn) {
        const row = btn.closest("tr");
        const dataAttr = row?.dataset.spec;
        if (!dataAttr) return;
        const data = JSON.parse(dataAttr);
        fillSpecForm(data);
        specModal?.show();
    }
    function showSpecCreate() {
        fillSpecForm({});
        specModal?.show();
    }
    async function saveSpec(event) {
        event.preventDefault();
        if (!specForm) return;
        const id = specForm.querySelector("#spec-id").value;
        const formData = new FormData(specForm);
        const url = id ? `/admin/spec/${id}` : "/admin/spec";
        const resp = await fetch(url, { method: "POST", body: formData });
        if (!resp.ok) {
            const msg = await resp.text();
            alert(`Ошибка при сохранении: ${msg}`);
            return;
        }
        specModal?.hide();
        location.reload();
    }
    async function deleteSpec(id) {
        if (!confirm("Удалить характеристику?")) return;
        const resp = await fetch(`/admin/spec/${id}/delete`, { method: "POST" });
        if (!resp.ok) {
            alert("Ошибка удаления");
            return;
        }
        location.reload();
    }
    if (specsTable) {
        specsTable.querySelectorAll(".btn-spec-edit").forEach((btn) => {
            btn.addEventListener("click", () => showSpecEdit(btn));
        });
        specsTable.querySelectorAll(".btn-spec-delete").forEach((btn) => {
            btn.addEventListener("click", () => {
                const row = btn.closest("tr");
                const dataAttr = row?.dataset.spec;
                if (!dataAttr) return;
                const data = JSON.parse(dataAttr);
                deleteSpec(data.id);
            });
        });
        addSpecBtn?.addEventListener("click", showSpecCreate);
        specForm?.addEventListener("submit", saveSpec);
        populateSpecsBtn?.addEventListener("click", async () => {
            if (!confirm("Сгенерировать характеристики из таблицы (уникальные значения)?")) return;
            const resp = await fetch("/admin/specs/auto-populate", { method: "POST" });
            if (!resp.ok) {
                alert("Ошибка авто-заполнения");
                return;
            }
            location.reload();
        });
        const syncSpecsBulk = () => {
            const selected = document.querySelectorAll(".spec-row-select:checked");
            if (bulkDeleteSpecsBtn) bulkDeleteSpecsBtn.disabled = selected.length === 0;
        };
        specsTable.querySelectorAll(".spec-row-select").forEach((chk) =>
            chk.addEventListener("change", () => {
                syncSpecsBulk();
                if (!chk.checked && selectAllSpecs) selectAllSpecs.checked = false;
            })
        );
        selectAllSpecs?.addEventListener("change", () => {
            const checked = selectAllSpecs.checked;
            specsTable.querySelectorAll(".spec-row-select").forEach((chk) => {
                chk.checked = checked;
            });
            syncSpecsBulk();
        });
        bulkDeleteSpecsBtn?.addEventListener("click", async () => {
            const ids = Array.from(document.querySelectorAll(".spec-row-select:checked")).map((el) =>
                parseInt(el.dataset.id, 10)
            );
            if (!ids.length) return;
            if (!confirm(`Удалить выбранные (${ids.length})?`)) return;
            const resp = await fetch("/admin/specs/bulk-delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids }),
            });
            if (!resp.ok) {
                alert("Ошибка массового удаления");
                return;
            }
            location.reload();
        });
        syncSpecsBulk();
    }
});
