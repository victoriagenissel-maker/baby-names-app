let index = 0;
let currentName = null;
let currentUser = localStorage.getItem("baby_user") || null;
let availableGenders = [];
let availableOrigins = [];
let selectedSwipeGenders = new Set();
let selectedSwipeOrigins = new Set();
let selectedListGenders = new Set();
let selectedListOrigins = new Set();
let userDisplayNames = { user1: "user1", user2: "user2" };
let currentPage = "swipe";

async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
        return;
    }

    try {
        const registration = await navigator.serviceWorker.register("/sw.js", {
            updateViaCache: "none"
        });
        await registration.update();
    } catch (err) {
        console.error("Service worker registration failed", err);
    }
}

function uniqueLower(values) {
    return new Set(values.map((value) => String(value).toLowerCase()));
}

function userCursorKey(user) {
    return `baby_cursor_${user}`;
}

function currentNameKey(user) {
    return `baby_current_name_${user}`;
}

function getStoredCursor(user) {
    const raw = localStorage.getItem(userCursorKey(user));
    return raw ? parseInt(raw, 10) : 0;
}

function setStoredCursor(user, value) {
    localStorage.setItem(userCursorKey(user), String(value));
}

function getStoredCurrentName(user) {
    return localStorage.getItem(currentNameKey(user));
}

function setStoredCurrentName(user, value) {
    if (value) {
        localStorage.setItem(currentNameKey(user), value);
    } else {
        localStorage.removeItem(currentNameKey(user));
    }
}

function getCheckedValues(groupName) {
    const checked = document.querySelectorAll(`input[name="${groupName}"]:checked`);
    return Array.from(checked).map((input) => input.value);
}

function readFiltersFromUI(context) {
    if (context === "swipe") {
        selectedSwipeGenders = uniqueLower(getCheckedValues("swipe-gender"));
        selectedSwipeOrigins = uniqueLower(getCheckedValues("swipe-origin"));
        return;
    }

    selectedListGenders = uniqueLower(getCheckedValues("list-gender"));
    selectedListOrigins = uniqueLower(getCheckedValues("list-origin"));
}

function onSwipeFiltersChanged() {
    readFiltersFromUI("swipe");
    if (!currentUser) {
        return;
    }

    index = 0;
    setStoredCursor(currentUser, index);
    loadName();
}

function onListFiltersChanged() {
    readFiltersFromUI("list");
    if (!currentUser) {
        return;
    }

    loadHistory();
}

function renderFilterOptions(containerId, name, values, selectedSet, onChangeHandler) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    values.forEach((value) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = name;
        input.value = value;
        const lowered = String(value).toLowerCase();
        input.checked = !selectedSet || selectedSet.size === 0 || selectedSet.has(lowered);
        input.addEventListener("change", onChangeHandler);

        label.appendChild(input);
        label.append(` ${value}`);
        container.appendChild(label);
    });

}

function setGroupChecked(context, groupName, checked) {
    const selectorName = `${context}-${groupName}`;
    const inputs = document.querySelectorAll(`input[name="${selectorName}"]`);
    inputs.forEach((input) => {
        input.checked = checked;
    });

    if (context === "swipe") {
        onSwipeFiltersChanged();
    } else {
        onListFiltersChanged();
    }
}

function getFilterState(context) {
    if (context === "swipe") {
        return {
            genders: selectedSwipeGenders,
            origins: selectedSwipeOrigins,
            onChangeHandler: onSwipeFiltersChanged,
            genderContainer: "swipe-gender-options",
            originContainer: "swipe-origin-options",
            genderName: "swipe-gender",
            originName: "swipe-origin"
        };
    }

    return {
        genders: selectedListGenders,
        origins: selectedListOrigins,
        onChangeHandler: onListFiltersChanged,
        genderContainer: "list-gender-options",
        originContainer: "list-origin-options",
        genderName: "list-gender",
        originName: "list-origin"
    };
}

function buildFilteredParams(context, includeCursor = false) {
    const params = new URLSearchParams({ user: currentUser });

    if (includeCursor) {
        params.set("cursor", String(index));
    }

    const state = getFilterState(context);
    const selectedGenders = state.genders;
    const selectedOrigins = state.origins;

    const allGendersSelected = selectedGenders.size === 0 ||
        selectedGenders.size === availableGenders.length;
    const allOriginsSelected = selectedOrigins.size === 0 ||
        selectedOrigins.size === availableOrigins.length;

    if (!allGendersSelected) {
        params.set("genders", Array.from(selectedGenders).join(","));
    }
    if (!allOriginsSelected) {
        params.set("origins", Array.from(selectedOrigins).join(","));
    }

    return params;
}

async function loadFilterCatalog() {
    const previousSwipeGenders = new Set(selectedSwipeGenders);
    const previousSwipeOrigins = new Set(selectedSwipeOrigins);
    const previousListGenders = new Set(selectedListGenders);
    const previousListOrigins = new Set(selectedListOrigins);

    const res = await fetch("/filters");
    const data = await res.json();
    availableGenders = data.genders || [];
    availableOrigins = data.origins || [];

    renderFilterOptions(
        "swipe-gender-options",
        "swipe-gender",
        availableGenders,
        previousSwipeGenders,
        onSwipeFiltersChanged
    );
    renderFilterOptions(
        "swipe-origin-options",
        "swipe-origin",
        availableOrigins,
        previousSwipeOrigins,
        onSwipeFiltersChanged
    );

    renderFilterOptions(
        "list-gender-options",
        "list-gender",
        availableGenders,
        previousListGenders,
        onListFiltersChanged
    );
    renderFilterOptions(
        "list-origin-options",
        "list-origin",
        availableOrigins,
        previousListOrigins,
        onListFiltersChanged
    );

    readFiltersFromUI("swipe");
    readFiltersFromUI("list");
}

function getDisplayName(user) {
    return userDisplayNames[user] || user;
}

function setStatus(message, isError = false) {
    const el = document.getElementById("settings-status");
    if (!el) {
        return;
    }
    el.innerText = message;
    el.classList.toggle("error-text", isError);
}

function showPage(page) {
    currentPage = page;
    const swipePage = document.getElementById("swipe-page");
    const settingsPage = document.getElementById("settings-page");
    const listsPage = document.getElementById("lists-page");

    if (page === "settings") {
        swipePage.classList.add("hidden");
        listsPage.classList.add("hidden");
        settingsPage.classList.remove("hidden");
    } else if (page === "lists") {
        swipePage.classList.add("hidden");
        settingsPage.classList.add("hidden");
        listsPage.classList.remove("hidden");
        loadHistory();
    } else {
        settingsPage.classList.add("hidden");
        listsPage.classList.add("hidden");
        swipePage.classList.remove("hidden");
    }
}

function refreshUserLabels() {
    const user1Btn = document.getElementById("login-user1-btn");
    const user2Btn = document.getElementById("login-user2-btn");
    user1Btn.innerText = `I am ${getDisplayName("user1")}`;
    user2Btn.innerText = `I am ${getDisplayName("user2")}`;

    if (currentUser) {
        document.getElementById("whoami").innerText =
            `Logged in as ${getDisplayName(currentUser)}`;
    }

    document.getElementById("user1-name").value = getDisplayName("user1");
    document.getElementById("user2-name").value = getDisplayName("user2");
}

async function loadUsers() {
    const res = await fetch("/users");
    const data = await res.json();
    userDisplayNames = {
        user1: data.user1 || "user1",
        user2: data.user2 || "user2"
    };
    refreshUserLabels();
}

async function saveUserNames() {
    const user1Name = document.getElementById("user1-name").value.trim();
    const user2Name = document.getElementById("user2-name").value.trim();

    if (!user1Name || !user2Name) {
        setStatus("Please enter both names.", true);
        return;
    }

    const res = await fetch("/users", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            user1_name: user1Name,
            user2_name: user2Name
        })
    });
    const data = await res.json();

    if (!res.ok) {
        setStatus(data.error || "Could not save names.", true);
        return;
    }

    userDisplayNames = {
        user1: data.users.user1 || "user1",
        user2: data.users.user2 || "user2"
    };
    refreshUserLabels();
    setStatus("Names saved.");
}

async function resetAllData() {
    const agreed = confirm("This will delete likes, dislikes, and matches for both users. Continue?");
    if (!agreed) {
        return;
    }

    const typed = prompt("Type RESET to confirm permanent deletion:");
    if (typed !== "RESET") {
        alert("Reset canceled. You must type RESET exactly.");
        return;
    }

    const res = await fetch("/reset", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ confirm: true })
    });
    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Could not reset data.");
        return;
    }

    ["user1", "user2"].forEach((user) => setStoredCursor(user, 0));
    index = 0;
    currentName = null;

    await loadHistory();
    await loadName();
}

async function submitSuggestion() {
    if (!currentUser) {
        return;
    }

    const name = document.getElementById("suggest-name").value.trim();
    const gender = document.getElementById("suggest-gender").value;
    const origin = document.getElementById("suggest-origin").value.trim();

    if (!name || !origin) {
        alert("Please fill name, gender, and origin.");
        return;
    }

    const res = await fetch("/suggestions", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            from_user: currentUser,
            name,
            gender,
            origin
        })
    });
    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Could not send suggestion.");
        return;
    }

    document.getElementById("suggest-name").value = "";
    document.getElementById("suggest-origin").value = "";
    await loadFilterCatalog();
    if (data.match) {
        const banner = document.getElementById("match-banner");
        banner.classList.remove("hidden");
        setTimeout(() => banner.classList.add("hidden"), 1500);
    }
    alert("Suggestion sent and added to your likes.");
    await loadHistory();
    await loadName();
}

function selectUser(user) {
    currentUser = user;
    localStorage.setItem("baby_user", user);
    index = getStoredCursor(user);

    document.getElementById("login").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    document.getElementById("whoami").innerText = `Logged in as ${getDisplayName(user)}`;
    showPage(currentPage);

    loadName();
    loadHistory();
}

function switchUser() {
    currentUser = null;
    currentName = null;
    localStorage.removeItem("baby_user");
    setStatus("");

    document.getElementById("app").classList.add("hidden");
    document.getElementById("login").classList.remove("hidden");
}

async function loadName() {
    if (!currentUser) {
        return;
    }

    const storedCurrentName = getStoredCurrentName(currentUser);
    if (storedCurrentName) {
        currentName = storedCurrentName;
        document.getElementById("card").innerText = storedCurrentName;
        return;
    }

    const params = buildFilteredParams("swipe", true);

    let res = await fetch(`/next?${params.toString()}`);
    let data = await res.json();

    if (data.done) {
        document.getElementById("card").innerText = "No more names";
        currentName = null;
        setStoredCurrentName(currentUser, null);
        return;
    }

    index = data.index ?? index;
    setStoredCursor(currentUser, index + 1);
    currentName = `${data.name} (${data.gender}, ${data.origin})`;
    setStoredCurrentName(currentUser, currentName);
    document.getElementById("card").innerText = currentName;
}

async function like() {
    if (!currentUser || !currentName) {
        return;
    }

    const visibleName = currentName.split(" (")[0];
    const res = await fetch("/like", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            user: currentUser,
            name: visibleName
        })
    });
    const data = await res.json();

    if (data.match) {
        const banner = document.getElementById("match-banner");
        banner.classList.remove("hidden");
        setTimeout(() => banner.classList.add("hidden"), 1500);
    }

    setStoredCurrentName(currentUser, null);
    await loadHistory();
    await loadName();
}

async function dislike() {
    if (!currentUser || !currentName) {
        return;
    }

    const visibleName = currentName.split(" (")[0];
    await fetch("/dislike", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            user: currentUser,
            name: visibleName
        })
    });

    setStoredCurrentName(currentUser, null);
    await loadHistory();
    await loadName();
}

async function moveNameToLike(name) {
    if (!currentUser) {
        return;
    }

    const res = await fetch("/like", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ user: currentUser, name })
    });
    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Could not move name to liked list.");
        return;
    }

    if (data.match) {
        const banner = document.getElementById("match-banner");
        banner.classList.remove("hidden");
        setTimeout(() => banner.classList.add("hidden"), 1500);
    }

    await loadHistory();
    await loadName();
}

async function moveNameToDislike(name) {
    if (!currentUser) {
        return;
    }

    const res = await fetch("/dislike", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ user: currentUser, name })
    });
    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Could not move name to disliked list.");
        return;
    }

    await loadHistory();
    await loadName();
}

function renderNameList(elementId, items, emptyText, mode = "plain") {
    const list = document.getElementById(elementId);
    list.innerHTML = "";

    if (!items.length) {
        const li = document.createElement("li");
        li.innerText = emptyText;
        list.appendChild(li);
        return;
    }

    items.forEach((item) => {
        const li = document.createElement("li");
        const text = document.createElement("span");
        text.innerText = `${item.name} (${item.gender}, ${item.origin})`;
        li.appendChild(text);

        if (mode === "likes") {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "mini-action";
            btn.innerText = "Move to Disliked";
            btn.onclick = () => moveNameToDislike(item.name);
            li.appendChild(btn);
        } else if (mode === "dislikes") {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "mini-action";
            btn.innerText = "Move to Liked";
            btn.onclick = () => moveNameToLike(item.name);
            li.appendChild(btn);
        }

        list.appendChild(li);
    });
}

function renderSuggestionList(items) {
    const list = document.getElementById("suggestions-list");
    list.innerHTML = "";

    if (!items.length) {
        const li = document.createElement("li");
        li.innerText = "No suggestions received yet";
        list.appendChild(li);
        return;
    }

    items.forEach((item) => {
        const li = document.createElement("li");
        li.innerText = `${item.name} (${item.gender}, ${item.origin}) from ${item.from_display_name}`;
        list.appendChild(li);
    });
}

function applyPrintSelection() {
    const mapping = [
        { checkboxId: "print-liked", cardId: "card-liked" },
        { checkboxId: "print-disliked", cardId: "card-disliked" },
        { checkboxId: "print-matched", cardId: "card-matched" },
        { checkboxId: "print-suggested", cardId: "card-suggested" }
    ];

    let selectedCount = 0;
    mapping.forEach(({ checkboxId, cardId }) => {
        const checkbox = document.getElementById(checkboxId);
        const card = document.getElementById(cardId);
        if (!checkbox || !card) {
            return;
        }

        if (checkbox.checked) {
            selectedCount += 1;
            card.classList.remove("print-exclude");
        } else {
            card.classList.add("print-exclude");
        }
    });

    return selectedCount;
}

function clearPrintSelection() {
    const cards = document.querySelectorAll(".list-card");
    cards.forEach((card) => card.classList.remove("print-exclude"));
}

function printSelectedLists() {
    showPage("lists");
    const selectedCount = applyPrintSelection();
    if (selectedCount === 0) {
        clearPrintSelection();
        alert("Select at least one list to print.");
        return;
    }

    const onAfterPrint = () => {
        clearPrintSelection();
        window.removeEventListener("afterprint", onAfterPrint);
    };
    window.addEventListener("afterprint", onAfterPrint);
    window.print();
}

async function loadHistory() {
    if (!currentUser) {
        return;
    }

    const params = buildFilteredParams("list", false);

    const res = await fetch(`/history?${params.toString()}`);
    const data = await res.json();

    renderNameList("likes-list", data.likes || [], "No liked names yet", "likes");
    renderNameList("dislikes-list", data.dislikes || [], "No disliked names yet", "dislikes");
    renderNameList("matches-list", data.matches || [], "No matches yet", "plain");

    const suggRes = await fetch(`/suggestions?${params.toString()}`);
    const suggestions = await suggRes.json();
    renderSuggestionList(Array.isArray(suggestions) ? suggestions : []);
}

async function boot() {
    registerServiceWorker();
    await Promise.all([loadFilterCatalog(), loadUsers()]);
    showPage("swipe");
    if (currentUser === "user1" || currentUser === "user2") {
        selectUser(currentUser);
    }
}

boot();