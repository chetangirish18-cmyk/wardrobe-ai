const clothingOptions = {
    "Jeans": { label: "What kind of jeans?", options: ["Straight-fit", "Baggy", "Bootcut"] },
    "Normal Pants": { label: "What fit?", options: ["Normal fit", "Loose fit"] },
    "Formal Pants": { label: "What fit?", options: ["Normal fit", "Slim fit", "Loose fit"] },
    "Cargo Pants": { label: "What fit?", options: ["Regular", "Loose", "Baggy"] },
    "Tracks": { label: "What fit?", options: ["Regular", "Loose", "Slim"] },
    "T-Shirt": { label: "What kind of T-shirt?", options: ["Plain", "Printed", "Oversized"] },
    "Shirt": { label: "What kind of shirt?", options: ["Plain", "Printed", "Checks", "Striped", "Oversized"] },
    "Zipper Sweatshirt": { label: "What fit?", options: ["Regular", "Oversized"] },
    "Zip Hoodie": { label: "What fit?", options: ["Regular", "Oversized"] },
    "Linen Shirt": { label: "What kind of linen shirt?", options: ["Plain", "Printed"] },
    "Sneakers": { label: "What type?", options: ["Casual", "Sports", "High-top", "Low-top"] },
    "Boots": { label: "What type?", options: ["Chelsea", "Casual", "Lace-up"] },
    "Casual Slippers": { label: "What type?", options: ["Basic", "Slides", "Strap"] }
};

let currentDetectedWeather = "mild";
let currentOccasion = "casual";
let currentFilter = "all";
let currentSearchQuery = "";
let currentOutfit = null;
let currentLooks = [];
let selectedDrawerItem = null;

async function uploadFile(fileInput) {
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) return "";
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const res = await fetch("/upload", { method: "POST", body: formData });
        const data = await res.json();
        return data.url || "";
    } catch (e) {
        console.error("Upload error:", e);
        return "";
    }
}

function setupAddPage() {
    const form = document.getElementById("clothingForm");
    const categoryGrid = document.getElementById("categoryGrid");
    const subtypeContainer = document.getElementById("subtypeContainer");
    const subtypeGrid = document.getElementById("subtypeGrid");
    const subtypeLabel = document.getElementById("subtypeLabel");

    if (!form || !categoryGrid) return;

    let selectedCategory = "";
    let selectedSubtype = "";

    const categoryButtons = categoryGrid.querySelectorAll(".category-button");

    categoryButtons.forEach(button => {
        button.addEventListener("click", () => {
            selectedCategory = button.dataset.category;
            selectedSubtype = "";

            categoryButtons.forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");

            const selected = clothingOptions[selectedCategory];
            if (!selected) return;

            if (subtypeContainer) subtypeContainer.style.display = "block";
            if (subtypeLabel) subtypeLabel.textContent = selected.label;

            if (subtypeGrid) {
                subtypeGrid.innerHTML = "";
                selected.options.forEach(option => {
                    const subtypeButton = document.createElement("button");
                    subtypeButton.type = "button";
                    subtypeButton.className = "subtype-button";
                    subtypeButton.textContent = option;
                    subtypeButton.dataset.subtype = option;

                    subtypeButton.addEventListener("click", () => {
                        selectedSubtype = option;
                        subtypeGrid.querySelectorAll(".subtype-button").forEach(btn => btn.classList.remove("active"));
                        subtypeButton.classList.add("active");
                    });

                    subtypeGrid.appendChild(subtypeButton);
                });
            }
        });
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const nameInput = document.getElementById("clothingName");
        const colorInput = document.getElementById("clothingColor");
        const fileInput = document.getElementById("clothingImage");

        const name = nameInput ? nameInput.value.trim() : "";
        const color = colorInput ? colorInput.value.trim() : "";
        const price = 0.0;

        if (!selectedCategory) { alert("Please select a category."); return; }
        if (!selectedSubtype) { alert("Please select the type / fit."); return; }
        if (!name) { alert("Please enter the clothing name."); if (nameInput) nameInput.focus(); return; }
        if (!color) { alert("Please enter the color."); if (colorInput) colorInput.focus(); return; }

        let image_url = "";
        if (fileInput && fileInput.files.length > 0) {
            image_url = await uploadFile(fileInput);
        }

        const data = { category: selectedCategory, subtype: selectedSubtype, name, color, price, image_url };

        try {
            const response = await fetch("/add-clothes", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });

            if (!response.ok) throw new Error(`Server returned ${response.status}`);
            const result = await response.json();

            if (!result.success) {
                alert(result.message || "Could not add the clothing.");
                return;
            }

            const modal = document.getElementById("successModal");
            const successMessage = document.getElementById("successMessage");
            if (successMessage) successMessage.textContent = `${name} was added to your wardrobe.`;
            if (modal) modal.classList.add("show");

            form.reset();
            selectedCategory = "";
            selectedSubtype = "";
            categoryButtons.forEach(btn => btn.classList.remove("active"));
            if (subtypeContainer) subtypeContainer.style.display = "none";
            if (subtypeGrid) subtypeGrid.innerHTML = "";

        } catch (error) {
            console.error("Add clothing error:", error);
            alert("Could not add the clothing. Please make sure the server is running.");
        }
    });

    const addAnotherButton = document.getElementById("addAnotherButton");
    if (addAnotherButton) {
        addAnotherButton.addEventListener("click", () => {
            const modal = document.getElementById("successModal");
            if (modal) modal.classList.remove("show");
        });
    }

    const viewWardrobeButton = document.getElementById("viewWardrobeButton");
    if (viewWardrobeButton) {
        viewWardrobeButton.addEventListener("click", () => {
            window.location.href = "/wardrobe";
        });
    }
}

function setupGreeting() {
    const titleEl = document.getElementById("greetingTitle");
    const textEl = document.getElementById("greetingText");

    if (!titleEl || !textEl) return;

    const greetings = [
        { title: "Hey.", subtitle: "Let's see what we're wearing today." },
        { title: "Hello.", subtitle: "Your wardrobe is waiting." },
        { title: "Hi.", subtitle: "Ready to build your collection?" },
        { title: "Hey there.", subtitle: "Let's keep your wardrobe organised." },
        { title: "Hello again.", subtitle: "Something new to wear?" },
        { title: "Hi.", subtitle: "Your clothes. Your style." }
    ];

    const selected = greetings[Math.floor(Math.random() * greetings.length)];
    titleEl.textContent = selected.title;
    textEl.textContent = selected.subtitle;
}

async function detectAutoWeather() {
    const weatherText = document.getElementById("weatherText");
    if (!weatherText) return;

    if (!navigator.geolocation) {
        weatherText.textContent = "Weather unavailable (Default: Mild)";
        currentDetectedWeather = "mild";
        checkDailyOutfit();
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async position => {
            try {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`);
                
                if (!res.ok) throw new Error("Weather request failed");
                const data = await res.json();
                
                const temp = data.current_weather.temperature;
                const code = data.current_weather.weathercode;
                const rainCodes = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99];
                
                if (rainCodes.includes(code)) {
                    currentDetectedWeather = "rainy";
                    weatherText.textContent = `${temp}°C · Rainy`;
                } else if (temp >= 28) {
                    currentDetectedWeather = "hot";
                    weatherText.textContent = `${temp}°C · Hot & Sunny`;
                } else if (temp >= 22) {
                    currentDetectedWeather = "warm";
                    weatherText.textContent = `${temp}°C · Warm`;
                } else if (temp >= 15) {
                    currentDetectedWeather = "mild";
                    weatherText.textContent = `${temp}°C · Mild`;
                } else {
                    currentDetectedWeather = "cool";
                    weatherText.textContent = `${temp}°C · Cool`;
                }
            } catch (err) {
                console.error("Auto weather error:", err);
                weatherText.textContent = "Weather offline (Default: Mild)";
                currentDetectedWeather = "mild";
            }
            checkDailyOutfit();
        },
        error => {
            console.warn("Location permission denied or unavailable:", error);
            weatherText.textContent = "Location off (Default: Mild)";
            currentDetectedWeather = "mild";
            checkDailyOutfit();
        }
    );
}

async function setupWardrobePage() {
    const clothesList = document.getElementById("clothesList");
    if (!clothesList) return;

    detectAutoWeather();
    await loadClothes();
    setupSearchAndFilters();
    setupOccasionSelector();
    setupOutfitButtons();
    setupEditModal();
}

async function loadClothes() {
    try {
        const response = await fetch("/clothes");
        if (!response.ok) throw new Error("Failed to load clothes");
        const clothes = await response.json();

        window.allClothes = clothes;
        updateStatsAndAnalytics(clothes);
        applySearchAndFilters();
    } catch (error) {
        console.error("Error loading clothes:", error);
    }
}

function updateStatsAndAnalytics(clothes) {
    const totalCount = document.getElementById("totalCount");
    const cleanCount = document.getElementById("cleanCount");
    const dirtyCount = document.getElementById("dirtyCount");
    const dirtyFilterBadge = document.getElementById("dirtyFilterBadge");
    const dirtyItems = clothes.filter(i => i.is_dirty === 1);
    const cleanItems = clothes.filter(i => i.is_dirty === 0);
    if (totalCount) totalCount.textContent = clothes.length;
    if (cleanCount) cleanCount.textContent = cleanItems.length;
    if (dirtyCount) dirtyCount.textContent = dirtyItems.length;
    if (dirtyFilterBadge) dirtyFilterBadge.textContent = dirtyItems.length;
    const sorted = [...clothes].sort((a,b) => (b.worn_count||0)-(a.worn_count||0));
    const most = sorted[0];
    const least = sorted[sorted.length-1];
    const mostEl=document.getElementById("mostWornName"), mostC=document.getElementById("mostWornCount");
    if (mostEl) mostEl.textContent=most?.name||"—";
    if (mostC) mostC.textContent=most ? `Worn ${most.worn_count} times` : "—";
    const leastEl=document.getElementById("leastWornName"), leastC=document.getElementById("leastWornCount");
    if (leastEl) leastEl.textContent=least?.name||"—";
    if (leastC) leastC.textContent=least ? `Worn ${least.worn_count} times` : "—";
    const unworn=document.getElementById("unwornCount");
    if (unworn) unworn.textContent=clothes.filter(i=>(i.worn_count||0)===0).length;
    const active=document.getElementById("activeRotation");
    if (active) active.textContent=clothes.filter(i=>i.last_worn && (Date.now()-new Date(i.last_worn).getTime())<=30*86400000).length;
    renderFavorites(clothes);
    loadStyleDNA();
    loadOutfitHistory();
}

async function loadStyleDNA(){
    try{ const r=await fetch('/style-dna'); const d=await r.json();
        const a=document.getElementById('dominantStyle'), b=document.getElementById('dominantStyleText'), c=document.getElementById('topColorInsight'), e=document.getElementById('rotationInsight');
        if(a)a.textContent=d.dominant_style||'—'; if(b)b.textContent=d.text||''; if(c)c.textContent=d.top_color||'—'; if(e)e.textContent=d.rotation||'0%';
        const bars=document.getElementById('colorBars'); if(bars){bars.innerHTML=(d.colors||[]).map(x=>`<div class="color-bar-row"><span>${escapeHtml(x.name)}</span><div><i style="width:${Math.max(8, x.count*100/Math.max(1,(d.colors||[])[0]?.count||1))}%"></i></div><b>${x.count}</b></div>`).join('');}
    }catch(e){console.error('Style DNA error',e)}
}

function renderFavorites(clothes){
    const grid=document.getElementById('favoriteGrid'), empty=document.getElementById('favoriteEmpty'); if(!grid)return;
    const favs=clothes.filter(i=>i.is_favorite); grid.innerHTML='';
    if(!favs.length){if(empty)empty.style.display='block'; return;}
    if(empty)empty.style.display='none';
    favs.forEach(item=>{const el=document.createElement('button'); el.className='mini-clothes-card'; el.innerHTML=`${item.image_url?`<img src="${item.image_url}" alt="">`:`<span>${getClothingIcon(item)}</span>`}<strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.color)}</small>`; el.onclick=()=>openItemDrawer(item); grid.appendChild(el);});
}

async function loadOutfitHistory(){
    const list=document.getElementById('historyList'), empty=document.getElementById('historyEmpty'); if(!list)return;
    try{const r=await fetch('/outfit-history?limit=30'); const rows=await r.json(); list.innerHTML='';
      if(!rows.length){if(empty)empty.style.display='block'; renderCalendar([]); return;} if(empty)empty.style.display='none';
      rows.forEach(row=>{const el=document.createElement('div'); el.className='history-row'; el.innerHTML=`<div><strong>${escapeHtml(row.top_name||'—')} + ${escapeHtml(row.bottom_name||'—')}</strong><span>${escapeHtml(row.shoes_name||'—')} · ${row.worn_date}</span></div><div class="history-feedback"><button onclick="sendFeedback(${row.id},1)">♡</button><button onclick="sendFeedback(${row.id},-1)">×</button></div>`; list.appendChild(el);});
      renderCalendar(rows);
    }catch(e){console.error('History error',e)}
}
function renderCalendar(rows){const grid=document.getElementById('calendarGrid'), title=document.getElementById('calendarMonth'); if(!grid)return; const now=new Date(); if(title)title.textContent=now.toLocaleString(undefined,{month:'long',year:'numeric'}); const first=new Date(now.getFullYear(),now.getMonth(),1), days=new Date(now.getFullYear(),now.getMonth()+1,0).getDate(); let html=''; const offset=(first.getDay()+6)%7; for(let i=0;i<offset;i++)html+='<span class="calendar-day muted"></span>'; for(let d=1;d<=days;d++){const ds=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`; const worn=rows.some(r=>r.worn_date===ds); const today=d===now.getDate(); html+=`<span class="calendar-day ${worn?'worn':''} ${today?'today':''}">${d}</span>`;} grid.innerHTML=html;}
async function sendFeedback(id,value){try{await fetch('/outfit-feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({outfit_id:id,feedback:value})});}catch(e){console.error(e)}}

function setupSearchAndFilters() {
    const buttons = document.querySelectorAll(".filter-button");
    const searchInput = document.getElementById("searchInput");

    buttons.forEach(button => {
        button.addEventListener("click", () => {
            buttons.forEach(btn => btn.classList.remove("active"));
            button.classList.add("active");

            currentFilter = button.dataset.filter.toLowerCase();
            applySearchAndFilters();
        });
    });

    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            currentSearchQuery = e.target.value.toLowerCase().trim();
            applySearchAndFilters();
        });
    }
}

function setupOccasionSelector() {
    const pills = document.querySelectorAll(".occasion-pill");
    pills.forEach(pill => {
        pill.addEventListener("click", () => {
            pills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentOccasion = pill.dataset.occasion;
            generateOutfit(false);
        });
    });
}

function applySearchAndFilters() {
    let clothes = window.allClothes || [];

    if (currentFilter === "shirts") {
        clothes = clothes.filter(item => ["T-Shirt", "Shirt", "Linen Shirt"].includes(item.category));
    } else if (currentFilter === "pants") {
        clothes = clothes.filter(item => ["Jeans", "Normal Pants", "Formal Pants", "Cargo Pants", "Tracks"].includes(item.category));
    } else if (currentFilter === "outerwear") {
        clothes = clothes.filter(item => ["Zipper Sweatshirt", "Zip Hoodie"].includes(item.category));
    } else if (currentFilter === "footwear") {
        clothes = clothes.filter(item => ["Sneakers", "Boots", "Casual Slippers"].includes(item.category));
    } else if (currentFilter === "dirty") {
        clothes = clothes.filter(item => item.is_dirty === 1);
    }

    if (currentSearchQuery) {
        clothes = clothes.filter(item => 
            item.name.toLowerCase().includes(currentSearchQuery) ||
            item.color.toLowerCase().includes(currentSearchQuery) ||
            item.category.toLowerCase().includes(currentSearchQuery) ||
            item.subtype.toLowerCase().includes(currentSearchQuery)
        );
    }

    renderClothes(clothes);
}

function getClothingIcon(item) {
    if (item.image_url) {
        return `<img src="${item.image_url}" alt="${escapeHtml(item.name)}" class="clothing-thumbnail">`;
    }
    const icons = {
        "Jeans": "👖", "Normal Pants": "👖", "Formal Pants": "👖", "Cargo Pants": "👖", "Tracks": "👖",
        "T-Shirt": "👕", "Shirt": "👔", "Linen Shirt": "👔",
        "Zipper Sweatshirt": "🧥", "Zip Hoodie": "🧥",
        "Sneakers": "👟", "Boots": "🥾", "Casual Slippers": "🩴"
    };
    return icons[item.category] || "👕";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function renderClothes(clothes) {
    const clothesList = document.getElementById("clothesList");
    const emptyWardrobe = document.getElementById("emptyWardrobe");

    if (!clothesList) return;
    clothesList.innerHTML = "";

    if (!clothes || clothes.length === 0) {
        if (emptyWardrobe && (!window.allClothes || window.allClothes.length === 0)) {
            emptyWardrobe.style.display = "block";
        } else {
            if (emptyWardrobe) emptyWardrobe.style.display = "none";
            clothesList.innerHTML = `<div class="no-results">No clothes found matching your search/filter.</div>`;
        }
        return;
    }

    if (emptyWardrobe) emptyWardrobe.style.display = "none";

    clothes.forEach(item => {
        const card = document.createElement("div");
        card.className = `clothing-card ${item.is_dirty ? 'is-dirty' : ''}`;
        
        const wornInfo = item.worn_count > 0 ? `<span>Worn ${item.worn_count}x</span>` : `<span>Never worn yet</span>`;

        const dirtyBtnLabel = item.is_dirty ? "🧺 Mark Clean" : "🧺 Mark Dirty";

        card.innerHTML = `
            <div class="clothing-card-top">
                <div class="clothing-icon">${getClothingIcon(item)}</div>
                <div class="card-actions">
                    <button class="action-btn favorite-btn" title="Favourite">${item.is_favorite ? "★" : "☆"}</button><button class="action-btn edit-btn" title="Edit">✏️</button>
                    <button class="action-btn delete-btn" title="Delete">🗑️</button>
                </div>
            </div>
            <div class="clothing-info">
                <div class="card-header-row">
                    <span class="clothing-category">${escapeHtml(item.category)}</span>
                    ${item.is_dirty ? '<span class="dirty-tag">IN LAUNDRY</span>' : ''}
                </div>
                <h3>${escapeHtml(item.name)}</h3>
                <p>${escapeHtml(item.subtype)} · <strong>${escapeHtml(item.color)}</strong></p>
                <div class="wear-badge">${wornInfo}</div>
                <button class="laundry-toggle-btn">${dirtyBtnLabel}</button>
            </div>
        `;

        card.querySelector(".favorite-btn").addEventListener("click", (e) => { e.stopPropagation(); toggleFavorite(item.id); });
        card.addEventListener("click", (e) => { if (!e.target.closest("button")) openItemDrawer(item); });
        card.querySelector(".delete-btn").addEventListener("click", () => deleteItem(item.id, item.name));
        card.querySelector(".edit-btn").addEventListener("click", () => openEditModal(item));
        card.querySelector(".laundry-toggle-btn").addEventListener("click", () => toggleLaundry(item.id));

        clothesList.appendChild(card);
    });
}

async function toggleLaundry(id) {
    try {
        const res = await fetch(`/clothes/${id}/toggle-laundry`, { method: "PUT" });
        const result = await res.json();
        if (result.success) {
            await loadClothes();
        }
    } catch (err) {
        console.error("Laundry toggle error:", err);
    }
}

async function deleteItem(id, name) {
    if (!confirm(`Are you sure you want to delete "${name}" from your wardrobe?`)) return;

    try {
        const res = await fetch(`/clothes/${id}`, { method: "DELETE" });
        const result = await res.json();

        if (result.success) {
            await loadClothes();
        } else {
            alert(result.message || "Could not delete item.");
        }
    } catch (err) {
        console.error("Delete error:", err);
        alert("Failed to delete item.");
    }
}

function setupEditModal() {
    const modal = document.getElementById("editModal");
    const form = document.getElementById("editForm");
    const cancelBtn = document.getElementById("cancelEditButton");

    if (!modal || !form) return;

    cancelBtn.addEventListener("click", () => modal.classList.remove("show"));

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = document.getElementById("editId").value;
        const name = document.getElementById("editName").value.trim();
        const color = document.getElementById("editColor").value.trim();
        const price = 0.0;
        const editImageFile = document.getElementById("editImage");

        const item = window.allClothes.find(c => c.id == id);
        if (!item) return;

        let image_url = item.image_url || "";
        if (editImageFile && editImageFile.files.length > 0) {
            image_url = await uploadFile(editImageFile);
        }

        const updatedData = {
            category: item.category,
            subtype: item.subtype,
            name: name,
            color: color,
            price: price,
            image_url: image_url
        };

        try {
            const res = await fetch(`/clothes/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedData)
            });
            const result = await res.json();

            if (result.success) {
                modal.classList.remove("show");
                await loadClothes();
            } else {
                alert(result.message || "Failed to update item.");
            }
        } catch (err) {
            console.error("Update error:", err);
            alert("Error updating item.");
        }
    });
}

function openEditModal(item) {
    const modal = document.getElementById("editModal");
    if (!modal) return;

    document.getElementById("editId").value = item.id;
    document.getElementById("editName").value = item.name;
    document.getElementById("editColor").value = item.color;
    modal.classList.add("show");
}

async function toggleFavorite(id){try{const r=await fetch(`/clothes/${id}/favorite`,{method:'PUT'});const d=await r.json();if(d.success)await loadClothes();}catch(e){console.error(e)}}

function openItemDrawer(item){
    selectedDrawerItem=item; const overlay=document.getElementById('drawerOverlay'), drawer=document.getElementById('itemDrawer'); if(!drawer)return;
    const img=document.getElementById('drawerImage'); if(img)img.innerHTML=item.image_url?`<img src="${item.image_url}" alt="">`:`<span>${getClothingIcon(item)}</span>`;
    document.getElementById('drawerName').textContent=item.name; document.getElementById('drawerMeta').textContent=`${item.category} · ${item.subtype} · ${item.color}`;
    document.getElementById('drawerWorn').textContent=`${item.worn_count||0}×`; document.getElementById('drawerLastWorn').textContent=item.last_worn||'Never'; document.getElementById('drawerStatus').textContent=item.is_dirty?'Laundry':'Ready';
    const fav=document.getElementById('drawerFavorite'); if(fav)fav.textContent=item.is_favorite?'★ Saved to favourites':'☆ Add to favourites';
    if(overlay)overlay.classList.add('show'); drawer.classList.add('show');
}
function closeItemDrawer(){document.getElementById('drawerOverlay')?.classList.remove('show');document.getElementById('itemDrawer')?.classList.remove('show');}
function setupDrawer(){document.getElementById('closeDrawer')?.addEventListener('click',closeItemDrawer);document.getElementById('drawerOverlay')?.addEventListener('click',closeItemDrawer);document.getElementById('drawerFavorite')?.addEventListener('click',async()=>{if(selectedDrawerItem){await toggleFavorite(selectedDrawerItem.id); selectedDrawerItem=(window.allClothes||[]).find(x=>x.id===selectedDrawerItem.id)||selectedDrawerItem; openItemDrawer(selectedDrawerItem);}});document.getElementById('drawerStyleAround')?.addEventListener('click',()=>selectedDrawerItem&&styleAround(selectedDrawerItem));}
async function styleAround(item){try{const r=await fetch(`/style-around/${item.id}?weather=${encodeURIComponent(currentDetectedWeather)}&occasion=${encodeURIComponent(currentOccasion)}`);const d=await r.json();const grid=document.getElementById('styleAroundGrid');if(grid){grid.innerHTML=(d.looks||[]).map((x,i)=>`<article class="style-around-look"><small>${escapeHtml(x.label||`LOOK ${i+1}`)}</small><h4>${escapeHtml(x.top.name)} + ${escapeHtml(x.bottom.name)}</h4><p>${escapeHtml(x.shoes.name)}</p><span>${escapeHtml(x.why||'Curated around your selected piece.')}</span></article>`).join('');}document.getElementById('styleAroundTitle').textContent=`Looks around ${item.name}`;document.getElementById('styleAroundModal').classList.add('show');}catch(e){console.error('Style around error',e)}}

function setupOutfitButtons() {
    const outfitButton=document.getElementById('outfitButton'), newButton=document.getElementById('newOutfitButton');
    if(outfitButton)outfitButton.addEventListener('click',()=>generateOutfit(false));
    if(newButton)newButton.addEventListener('click',()=>generateOutfit(true));
    setupDrawer();
}
function getTodayKey(){return `dailyOutfit_${new Date().toISOString().split('T')[0]}`;}
function checkDailyOutfit(){const saved=localStorage.getItem(getTodayKey());if(saved){try{const d=JSON.parse(saved);currentOutfit=d;displayOutfit(d);return}catch(e){localStorage.removeItem(getTodayKey())}}}
async function generateOutfit(isNew=false){
    const section=document.getElementById('outfitSection'), msg=document.getElementById('outfitMessage');
    try{const exclude=isNew&&window.lastOutfitKeys?window.lastOutfitKeys.join(','):''; const r=await fetch(`/recommend-outfit?weather=${encodeURIComponent(currentDetectedWeather)}&occasion=${encodeURIComponent(currentOccasion)}&exclude=${encodeURIComponent(exclude)}`); const d=await r.json(); if(!d.success){if(msg)msg.textContent=d.message;section.style.display='block';return;} currentLooks=d.looks||[]; currentOutfit=currentLooks[0]; window.lastOutfitKeys=currentLooks.map(x=>x.outfitKey); localStorage.setItem(getTodayKey(),JSON.stringify(d)); displayOutfit(d);}catch(e){console.error(e);if(msg)msg.textContent='Could not create your looks right now.';section.style.display='block';}}
function renderOutfitSlot(item, icon){return item?.image_url?`<img src="${item.image_url}" class="outfit-thumbnail" alt="${escapeHtml(item.name)}">`:`<span>${icon}</span>`;}
function displayOutfit(result){
    const section=document.getElementById('outfitSection'), grid=document.getElementById('outfitAlternatives'); if(section)section.style.display='block'; if(!grid)return;
    document.getElementById('outfitMessage').textContent=result.message||'Three options from your wardrobe.';
    const looks=result.looks||[result]; currentLooks=looks; currentOutfit=looks[0];
    grid.innerHTML=looks.map((x,i)=>`<article class="outfit-look-card ${i===0?'selected':''}" data-index="${i}"><div class="look-label">${escapeHtml(x.label||`LOOK ${i+1}`)}</div><div class="look-visuals"><div>${renderOutfitSlot(x.top,'👕')}<small>TOP</small></div><div>${renderOutfitSlot(x.bottom,'👖')}<small>BOTTOM</small></div><div>${renderOutfitSlot(x.shoes,'👟')}<small>SHOES</small></div></div><h3>${escapeHtml(x.top.name)} + ${escapeHtml(x.bottom.name)}</h3><p>${escapeHtml(x.shoes.name)}</p><span class="look-why">${escapeHtml(x.why||'Balanced for your occasion and weather.')}</span><button class="select-look-btn">${i===0?'✓ Selected':'Select this look'}</button></article>`).join('');
    grid.querySelectorAll('.outfit-look-card').forEach((card,i)=>card.querySelector('.select-look-btn').addEventListener('click',()=>{grid.querySelectorAll('.outfit-look-card').forEach(c=>c.classList.remove('selected'));card.classList.add('selected');currentOutfit=looks[i];grid.querySelectorAll('.select-look-btn').forEach((b,j)=>b.textContent=j===i?'✓ Selected':'Select this look');}));
}
async function logOutfitWorn(){if(!currentOutfit)return;try{const r=await fetch('/wear-outfit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({top_id:currentOutfit.top.id,bottom_id:currentOutfit.bottom.id,shoes_id:currentOutfit.shoes.id})});const d=await r.json();if(d.success){document.getElementById('wornConfirmation').hidden=false;await loadClothes();}}catch(e){console.error('Wear log error',e)}}

function setupBackupRestore() {
    const exportBtn = document.getElementById("exportBackupBtn");
    const importInput = document.getElementById("importBackupInput");

    if (exportBtn) {
        exportBtn.addEventListener("click", () => {
            window.location.href = "/backup";
        });
    }

    if (importInput) {
        importInput.addEventListener("change", async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            if (!confirm("Restoring a backup will replace your current wardrobe data. Continue?")) {
                importInput.value = "";
                return;
            }

            const formData = new FormData();
            formData.append("file", file);

            try {
                const response = await fetch("/restore", {
                    method: "POST",
                    body: formData
                });

                const result = await response.json();
                if (result.success) {
                    alert("Wardrobe successfully restored!");
                    await loadClothes();
                } else {
                    alert(result.detail || "Failed to restore backup.");
                }
            } catch (error) {
                console.error("Restore error:", error);
                alert("Error restoring backup file.");
            } finally {
                importInput.value = "";
            }
        });
    }
}



// =========================================================
// ACCOUNT / PASSWORD AUTHENTICATION
// =========================================================
async function apiJSON(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Not authenticated");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || `Request failed (${response.status})`);
    return data;
}

async function loadCurrentUser() {
    try {
        const data = await fetch("/auth/me").then(r => r.json());
        if (!data.authenticated) {
            if (!location.pathname.startsWith("/login")) window.location.href = "/login";
            return null;
        }
        const el = document.getElementById("navUserPhone");
        if (el && data.user?.phone) {
            const phone = data.user.phone;
            el.textContent = phone.length > 6 ? `${phone.slice(0, 3)} •••• ${phone.slice(-4)}` : phone;
        }
        return data.user;
    } catch (e) {
        console.error("Auth check failed", e);
        return null;
    }
}

function setupLogout() {
    const button = document.getElementById("logoutButton");
    if (!button) return;
    button.addEventListener("click", async () => {
        try { await fetch("/auth/logout", { method: "POST" }); } finally { window.location.href = "/login"; }
    });
}

function setupLoginPage() {
    const form = document.getElementById("authForm");
    if (!form) return;

    const phoneInput = document.getElementById("phone");
    const passwordInput = document.getElementById("password");
    const confirmInput = document.getElementById("confirmPassword");
    const confirmWrap = document.getElementById("confirmWrap");
    const message = document.getElementById("authMessage");
    const title = document.getElementById("authTitle");
    const subtitle = document.getElementById("authSubtitle");
    const submit = document.getElementById("authSubmit");
    const loginTab = document.getElementById("loginTab");
    const signupTab = document.getElementById("signupTab");
    let mode = "login";

    phoneInput?.addEventListener("input", () => {
        phoneInput.value = phoneInput.value.replace(/\D/g, "").slice(0, 10);
    });

    function setMode(nextMode) {
        mode = nextMode;
        const signup = mode === "signup";
        loginTab.classList.toggle("active", !signup);
        signupTab.classList.toggle("active", signup);
        confirmWrap.style.display = signup ? "block" : "none";
        confirmInput.required = signup;
        passwordInput.autocomplete = signup ? "new-password" : "current-password";
        title.textContent = signup ? "Create your closet." : "Welcome back.";
        subtitle.textContent = signup
            ? "Create your account with a mobile number and password. No OTP required."
            : "Sign in with your mobile number and password to access your private wardrobe.";
        submit.innerHTML = signup ? 'Create account <span>→</span>' : 'Log in <span>→</span>';
        message.textContent = "";
        message.className = "auth-message";
        passwordInput.value = "";
        confirmInput.value = "";
    }

    loginTab?.addEventListener("click", () => setMode("login"));
    signupTab?.addEventListener("click", () => setMode("signup"));

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const phone = phoneInput.value.replace(/\D/g, "");
        const password = passwordInput.value;
        if (phone.length !== 10) {
            message.textContent = "Enter a valid 10-digit Indian mobile number.";
            message.className = "auth-message error";
            return;
        }
        if (password.length < 8) {
            message.textContent = "Password must be at least 8 characters.";
            message.className = "auth-message error";
            return;
        }
        if (mode === "signup" && password !== confirmInput.value) {
            message.textContent = "Passwords do not match.";
            message.className = "auth-message error";
            return;
        }
        try {
            submit.disabled = true;
            submit.textContent = mode === "signup" ? "Creating…" : "Signing in…";
            message.textContent = "";
            const endpoint = mode === "signup" ? "/auth/signup" : "/auth/login";
            const body = mode === "signup"
                ? { phone, password, confirm_password: confirmInput.value }
                : { phone, password };
            await apiJSON(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            window.location.href = "/";
        } catch (err) {
            message.textContent = err.message || "Could not complete authentication.";
            message.className = "auth-message error";
        } finally {
            submit.disabled = false;
            submit.innerHTML = mode === "signup" ? 'Create account <span>→</span>' : 'Log in <span>→</span>';
        }
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    if (location.pathname === "/login") { setupLoginPage(); return; }
    const user = await loadCurrentUser();
    if (!user) return;
    setupLogout();
    setupAddPage();
    setupGreeting();
    setupWardrobePage();
    setupBackupRestore();
});