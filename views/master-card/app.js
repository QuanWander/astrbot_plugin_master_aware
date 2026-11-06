const bridge = window.AstrBotPluginView;
const $ = (id) => document.getElementById(id);

const els = {
  masterName: $("masterName"),
  masterQq: $("masterQq"),
  days: $("days"),
  memoryCount: $("memoryCount"),
  lastSeen: $("lastSeen"),
  presetNow: $("presetNow"),
  presets: $("presets"),
  memories: $("memories"),
  memHint: $("memHint"),
  memInput: $("memInput"),
  memAdd: $("memAdd"),
  preview: $("preview"),
  previewBtn: $("previewBtn"),
  toast: $("toast"),
};

let toastTimer = null;
function toast(text, bad = false) {
  els.toast.textContent = text;
  els.toast.style.background = bad ? "#8e3b46" : "#3d2f35";
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { els.toast.hidden = true; }, 2200);
}

function fmtDate(value) {
  if (!value) return "—";
  return String(value).slice(0, 16);
}

async function loadStatus() {
  const data = await bridge.apiGet("status");
  const masters = data.masters || [];
  els.masterName.textContent = masters.length ? masters[0] : "未绑定";
  els.masterQq.textContent = masters.length ? `称呼：${data.title} · QQ ${masters[0]}` : "私聊发 /认主 绑定";
  els.days.textContent = data.days || "—";
  els.memoryCount.textContent = data.memory_count ?? "—";
  els.lastSeen.textContent = fmtDate(data.last_seen);
  els.presetNow.textContent = `当前：${data.preset || "默认"}`;
  for (const btn of els.presets.querySelectorAll("button")) {
    btn.classList.toggle("active", btn.dataset.preset === data.preset);
  }
}

async function loadMemories() {
  const data = await bridge.apiGet("memories");
  const list = data.memories || [];
  els.memHint.textContent = list.length ? `${list.length} 条` : "";
  els.memories.innerHTML = "";
  if (!list.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "还没有记忆。";
    els.memories.appendChild(li);
    return;
  }
  for (const item of list) {
    const li = document.createElement("li");
    const id = document.createElement("span");
    id.className = "id";
    id.textContent = item.id || "";
    const text = document.createElement("span");
    text.className = "txt";
    text.textContent = item.text || "";
    const del = document.createElement("button");
    del.className = "del";
    del.type = "button";
    del.textContent = "删除";
    del.addEventListener("click", async () => {
      try {
        await bridge.apiPost("memories/delete", { id: item.id });
        toast("删掉了");
        await loadMemories();
        await loadStatus();
      } catch (error) {
        toast("删除失败：" + error.message, true);
      }
    });
    li.append(id, text, del);
    els.memories.appendChild(li);
  }
}

async function loadPreview() {
  const data = await bridge.apiGet("preview");
  const parts = [data.note, data.guard, data.identity].filter(Boolean);
  els.preview.textContent = parts.join("\n\n");
}

async function addMemory() {
  const text = els.memInput.value.trim();
  if (!text) return;
  els.memAdd.disabled = true;
  try {
    const data = await bridge.apiPost("memories/add", { text });
    if (data.ok) {
      els.memInput.value = "";
      toast("记下了");
      await loadMemories();
      await loadStatus();
      await loadPreview();
    } else {
      toast(data.error || "没记上", true);
    }
  } catch (error) {
    toast("记不上：" + error.message, true);
  } finally {
    els.memAdd.disabled = false;
  }
}

async function setPreset(name) {
  try {
    const data = await bridge.apiPost("preset", { preset: name });
    if (data.ok) {
      toast(`已切换到「${name}」`);
      await loadStatus();
    } else {
      toast("切换失败", true);
    }
  } catch (error) {
    toast("切换失败：" + error.message, true);
  }
}

els.memAdd.addEventListener("click", addMemory);
els.memInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") addMemory();
});
els.previewBtn.addEventListener("click", loadPreview);
for (const btn of els.presets.querySelectorAll("button")) {
  btn.addEventListener("click", () => setPreset(btn.dataset.preset));
}

if (!bridge) {
  toast("页面没接到插件接口", true);
} else {
  await bridge.ready();
  await loadStatus();
  await loadMemories();
  await loadPreview();
}
