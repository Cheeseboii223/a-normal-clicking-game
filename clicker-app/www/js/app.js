'use strict';

/* =========================================================
   UTILITIES
   ========================================================= */
function formatNumber(value) {
  value = Math.trunc(Number(value) || 0);
  const sign = value < 0 ? '-' : '';
  value = Math.abs(value);
  if (value < 1000) return `${sign}${value}`;
  const units = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M'], [1e3, 'K']];
  for (const [threshold, suffix] of units) {
    if (value >= threshold) {
      let text = (value / threshold).toFixed(2);
      text = text.replace(/0+$/, '').replace(/\.$/, '');
      return `${sign}${text}${suffix}`;
    }
  }
  return `${sign}${value}`;
}

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }

// Retriggers a CSS animation on an element by removing + re-adding a class.
function bump(element, className) {
  element.classList.remove(className);
  void element.offsetWidth; // force reflow so the animation restarts
  element.classList.add(className);
}

const SAVE_KEY = 'clicker_save_v1';

/* =========================================================
   STATE
   ========================================================= */
function defaultState() {
  return {
    click_count: 0,
    milestones_unlocked: [],
    clicks_per_tap: 1,
    upgrade_level: 0,
    auto_click_level: 0,
    auto_click_rate: 0,
    server_mining_level: 0,
    mining_efficiency: 0,
    overclock_level: 0,
    cooling_level: 0,
    psu_boost_level: 0,
    ram_boost_level: 0,
    gpu_boost_level: 0,
    network_level: 0,
    cache_level: 0,
    core_level: 0,
    server_online: false,
    combo_streak: 0,
    last_tap_time: 0,
    combo_boost_level: 0,
    highest_click_count: 0,
    best_combo_streak: 0,
    hack_battles_won: 0,
    total_playtime_seconds: 0,
    last_seen_time: Date.now() / 1000,
    sound_enabled: true,
    music_enabled: true,
    server_build: { CPU: null, Motherboard: null, RAM: null, GPU: null, PSU: null, Case: null },
    offline_bonus_total: 0,
  };
}

let S = defaultState();

/* Saving is throttled: taps/ticks schedule a batched save instead of
   hitting localStorage synchronously every time, which keeps rapid
   tapping smooth. Important events (purchases, milestones, settings,
   pausing/backgrounding) still save immediately so nothing is lost. */
let saveScheduled = false;
function scheduleSave() {
  if (saveScheduled) return;
  saveScheduled = true;
  setTimeout(() => { saveScheduled = false; saveProgress(); }, 1200);
}

function saveProgress() {
  S.last_seen_time = Date.now() / 1000;
  const payload = { ...S, server_build: {} };
  for (const cat of SERVER_CATEGORIES) {
    const part = S.server_build[cat];
    payload.server_build[cat] = part ? part.name : null;
  }
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(payload)); } catch (e) { /* storage unavailable */ }
}

function loadProgress() {
  let data = null;
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (raw) data = JSON.parse(raw);
  } catch (e) { data = null; }

  if (!data) { S = defaultState(); recomputeStats(); return; }

  const d = defaultState();
  for (const key of Object.keys(d)) {
    if (key === 'server_build') continue;
    if (data[key] !== undefined) d[key] = data[key];
  }
  d.server_build = { CPU: null, Motherboard: null, RAM: null, GPU: null, PSU: null, Case: null };
  const rawBuild = data.server_build || {};
  for (const cat of SERVER_CATEGORIES) {
    const partName = rawBuild[cat];
    if (!partName) continue;
    const found = SERVER_PARTS[cat].find((p) => p.name === partName);
    if (found) d.server_build[cat] = found;
  }
  d.milestones_unlocked = (data.milestones_unlocked || []).filter((m) => MILESTONE_MESSAGES[m] !== undefined);
  S = d;
  recomputeStats();
  applyOfflineGain();
  S.highest_click_count = Math.max(S.highest_click_count, S.click_count);
}

function applyOfflineGain() {
  const now = Date.now() / 1000;
  const elapsed = Math.max(0, now - S.last_seen_time);
  if (elapsed <= 0) { S.offline_bonus_total = 0; return; }
  let gain = Math.trunc(elapsed / 20) + S.server_mining_level * 2;
  if (S.server_online && isServerBuildCompatible()) {
    gain += Math.trunc(getServerPowerScore() / 80);
  }
  S.click_count += gain;
  S.offline_bonus_total = gain;
  S.last_seen_time = now;
  saveProgress();
}

/* =========================================================
   SOUND (Web Audio beeps) + MUSIC
   ========================================================= */
let audioCtx = null;
function beep(frequency, durationMs, delayMs = 0) {
  if (!S.sound_enabled) return;
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const t0 = audioCtx.currentTime + delayMs / 1000;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'square';
    osc.frequency.value = frequency;
    gain.gain.setValueAtTime(0.06, t0);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + durationMs / 1000);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(t0);
    osc.stop(t0 + durationMs / 1000 + 0.02);
  } catch (e) { /* audio unavailable */ }
}
function playUiSound(kind = 'tap') {
  const tones = {
    tap: [[640, 40], [820, 35]],
    upgrade: [[420, 60], [620, 40], [820, 50]],
    server: [[240, 80], [520, 60], [760, 70]],
    reset: [[180, 80], [120, 120]],
    deny: [[220, 90]],
    rank: [[520, 60], [700, 60], [900, 90]],
  };
  let delay = 0;
  for (const [freq, dur] of (tones[kind] || tones.tap)) {
    beep(freq, dur, delay);
    delay += dur;
  }
}

const MUSIC_TRACKS = ['assets/music1.ogg', 'assets/music2.ogg'];
let musicTrackIndex = 0;
const bgAudio = document.getElementById('bg-audio');
bgAudio.volume = 0.5;
bgAudio.addEventListener('ended', () => {
  if (!S.music_enabled) return;
  musicTrackIndex = (musicTrackIndex + 1) % MUSIC_TRACKS.length;
  playMusicTrack(musicTrackIndex);
});
function playMusicTrack(index) {
  musicTrackIndex = index % MUSIC_TRACKS.length;
  bgAudio.src = MUSIC_TRACKS[musicTrackIndex];
  bgAudio.play().catch(() => { /* needs a user gesture first - fine, retried on next tap */ });
}
function stopMusic() { bgAudio.pause(); }
function toggleMusic(enabled) {
  S.music_enabled = enabled;
  if (enabled) playMusicTrack(musicTrackIndex); else stopMusic();
  saveProgress();
}

/* =========================================================
   RANK
   ========================================================= */
function getRankIndex() {
  let index = 0;
  for (let i = 0; i < RANK_THRESHOLDS.length; i++) {
    if (S.highest_click_count >= RANK_THRESHOLDS[i]) index = i; else break;
  }
  return index;
}
function getRankName() { return RANK_TIERS[getRankIndex()]; }
function getNextRankRequirement() {
  const index = getRankIndex();
  if (index >= RANK_THRESHOLDS.length - 1) return null;
  return RANK_THRESHOLDS[index + 1] - S.highest_click_count;
}
function getRankMultiplier() { return 1.0 + getRankIndex() * 0.02; }

/* =========================================================
   COMBO
   RAM Boost is the sole upgrade that touches combo: it widens the
   tap-timing window and raises the max combo cap. Nothing else
   writes to combo state, so it can never be "overwritten" by a
   different upgrade purchase.
   ========================================================= */
function getComboWindowSeconds() { return 0.9 + S.ram_boost_level * 0.015; }
function getComboCap() { return 5 + Math.floor(S.ram_boost_level / 3); }
function getComboMultiplier() {
  const now = Date.now() / 1000;
  if (now - S.last_tap_time < getComboWindowSeconds()) S.combo_streak += 1; else S.combo_streak = 1;
  S.last_tap_time = now;
  if (S.combo_streak > S.best_combo_streak) S.best_combo_streak = S.combo_streak;
  return 1 + Math.min(getComboCap(), S.combo_streak) * (0.15 + S.combo_boost_level * 0.05);
}

/* =========================================================
   UPGRADE COSTS
   ========================================================= */
const getClickUpgradeCost = () => Math.round(50 * 2 ** S.upgrade_level);
const getAutoClickCost = () => Math.round(250 * 2 ** S.auto_click_level);
const getServerMiningCost = () => Math.round(500 * 2 ** S.server_mining_level);
const getMiningEfficiencyCost = () => Math.round(900 * 2 ** S.mining_efficiency);
const getOverclockCost = () => Math.round(950 * 2 ** S.overclock_level);
const getCoolingCost = () => Math.round(1200 * 2 ** S.cooling_level);
const getPsuBoostCost = () => Math.round(1350 * 2 ** S.psu_boost_level);
const getRamBoostCost = () => Math.round(1500 * 2 ** S.ram_boost_level);
const getGpuBoostCost = () => Math.round(1800 * 2 ** S.gpu_boost_level);
const getNetworkCost = () => Math.round(1700 * 2 ** S.network_level);
const getCacheCost = () => Math.round(1650 * 2 ** S.cache_level);
const getCoreCost = () => Math.round(2200 * 2 ** S.core_level);

/* =========================================================
   DERIVED PRODUCTION STATS
   Every upgrade below owns exactly one effect. The only upgrade that
   touches more than one stat is "Core Overclock", and it does so as a
   clearly-labelled global percentage multiplier applied on top of
   everything else - never by silently adding into another upgrade's
   own number. This is what actually fixes the old bug where buying
   one upgrade could make another upgrade's displayed effect appear to
   "vanish": in the old build several upgrades quietly added into the
   same shared counter, so the number shown next to one upgrade didn't
   match what was actually being produced.
   ========================================================= */
function getClicksPerTap() {
  const flat = 1 + S.upgrade_level;
  const overclockMult = 1 + S.overclock_level * 0.03;
  const coreMult = 1 + S.core_level * 0.01;
  return flat * overclockMult * coreMult;
}
function getAutoClickRate() {
  const flat = S.auto_click_level;
  if (flat <= 0) return 0;
  const coolingMult = 1 + S.cooling_level * 0.03;
  const coreMult = 1 + S.core_level * 0.01;
  return flat * coolingMult * coreMult;
}
function recomputeStats() {
  S.clicks_per_tap = getClicksPerTap();
  S.auto_click_rate = getAutoClickRate();
}

const UPGRADE_ROWS = [
  {
    kind: 'click', name: 'Click Power', levelKey: 'upgrade_level', cost: getClickUpgradeCost,
    effect: () => `+1 click per tap  →  ${formatNumber(getClicksPerTap())}/tap now`,
  },
  {
    kind: 'auto', name: 'Auto Clicker', levelKey: 'auto_click_level', cost: getAutoClickCost,
    effect: () => `+1 auto-click/sec  →  ${formatNumber(getAutoClickRate())}/sec now`,
  },
  {
    kind: 'overclock', name: 'Overclock', levelKey: 'overclock_level', cost: getOverclockCost,
    effect: () => `+3% tap power  →  x${(1 + S.overclock_level * 0.03).toFixed(2)}`,
  },
  {
    kind: 'cooling', name: 'Cooling', levelKey: 'cooling_level', cost: getCoolingCost,
    effect: () => `+3% auto-click rate  →  x${(1 + S.cooling_level * 0.03).toFixed(2)}`,
  },
  {
    kind: 'mining', name: 'Mining Rig', levelKey: 'server_mining_level', cost: getServerMiningCost,
    effect: () => 'Raises server mining chance & payout floor',
  },
  {
    kind: 'efficiency', name: 'Mining Efficiency', levelKey: 'mining_efficiency', cost: getMiningEfficiencyCost,
    effect: () => 'Raises server mining chance & payout floor',
  },
  {
    kind: 'psu', name: 'PSU Boost', levelKey: 'psu_boost_level', cost: getPsuBoostCost,
    effect: () => `+15 server power score  →  helps builds run & mine more`,
  },
  {
    kind: 'ram', name: 'RAM Boost', levelKey: 'ram_boost_level', cost: getRamBoostCost,
    effect: () => `Widens combo window & raises combo cap to x${getComboCap()}`,
  },
  {
    kind: 'gpu', name: 'GPU Boost', levelKey: 'gpu_boost_level', cost: getGpuBoostCost,
    effect: () => '+18 mining power, +1 hack-battle attack',
  },
  {
    kind: 'network', name: 'Network Defense', levelKey: 'network_level', cost: getNetworkCost,
    effect: () => `Blocks ${S.network_level * 4} clicks stolen per hack, +1 attack`,
  },
  {
    kind: 'cache', name: 'Cache', levelKey: 'cache_level', cost: getCacheCost,
    effect: () => '+9 mining power  →  bigger mining payouts',
  },
  {
    kind: 'core', name: 'Core Overclock', levelKey: 'core_level', cost: getCoreCost,
    effect: () => `Global boost: +1% to ALL production  →  x${(1 + S.core_level * 0.01).toFixed(2)}`,
  },
];

function buyUpgrade(kind) {
  const map = {
    click: () => { S.upgrade_level++; },
    auto: () => { S.auto_click_level++; },
    mining: () => { S.server_mining_level++; },
    efficiency: () => { S.mining_efficiency++; },
    overclock: () => { S.overclock_level++; },
    cooling: () => { S.cooling_level++; },
    psu: () => { S.psu_boost_level++; },
    ram: () => { S.ram_boost_level++; },
    gpu: () => { S.gpu_boost_level++; },
    network: () => { S.network_level++; },
    cache: () => { S.cache_level++; },
    core: () => { S.core_level++; },
  };
  const row = UPGRADE_ROWS.find((r) => r.kind === kind);
  const cost = row.cost();
  if (S.click_count < cost) return false;
  S.click_count -= cost;
  map[kind]();
  recomputeStats();
  refreshClickLabel();
  saveProgress();
  return true;
}

/* =========================================================
   HACK ATTACK / STEAL POWER
   ========================================================= */
function getHackAttackPower() {
  let power = Math.max(1, Math.round(getClicksPerTap()));
  power += S.gpu_boost_level + S.network_level + S.combo_boost_level;
  if (S.server_online && isServerBuildCompatible()) power += 2 + Math.trunc(getServerPowerScore() / 180);
  power = Math.round(power * (1 + S.core_level * 0.01));
  return Math.max(1, power);
}
function getHackStealReduction() { return S.network_level * 4; }
function getExtraClickGain() { return 0; }

/* =========================================================
   SERVER BUILDER
   ========================================================= */
function getServerPowerScore(build = S.server_build) {
  let total = S.psu_boost_level * 15;
  for (const cat of SERVER_CATEGORIES) {
    const part = build[cat];
    if (part) total += part.power || 0;
  }
  return total;
}
function isServerBuildCompatible(build = S.server_build) {
  for (const cat of SERVER_CATEGORIES) if (!build[cat]) return false;
  const { CPU: cpu, Motherboard: mobo, RAM: ram, GPU: gpu, PSU: psu, Case: kase } = build;
  if (cpu.socket !== mobo.socket) return false;
  if (ram.generation !== mobo.memory_generation) return false;
  if (!kase.supports.includes(mobo.form_factor)) return false;
  if (gpu.length > kase.gpu_max_length) return false;
  const totalWattage = cpu.tdp + gpu.power_draw + ram.capacity * 0.5 + 120;
  if (psu.watts < totalWattage) return false;
  return true;
}
function getServerStatusText(build = S.server_build) {
  if (SERVER_CATEGORIES.some((cat) => !build[cat])) return 'Missing parts';
  if (isServerBuildCompatible(build)) return 'Build ready';
  if (build.CPU.socket !== build.Motherboard.socket) return 'CPU socket mismatch';
  if (build.RAM.generation !== build.Motherboard.memory_generation) return 'RAM and motherboard mismatch';
  if (!build.Case.supports.includes(build.Motherboard.form_factor)) return 'Board too big for case';
  if (build.GPU.length > build.Case.gpu_max_length) return 'GPU too long for case';
  if (build.PSU.watts < build.CPU.tdp + build.GPU.power_draw + 120) return 'PSU too weak';
  return 'Build invalid';
}
/* Mining reward is fed only by upgrades whose job is mining: Mining
   Rig, Mining Efficiency, GPU Boost and Cache, plus the server's own
   power score (parts + PSU Boost). Core Overclock's global multiplier
   is applied last, on top, same as everywhere else. */
function getServerMiningReward() {
  if (!S.server_online) return 0;
  if (!isServerBuildCompatible() || SERVER_CATEGORIES.some((c) => !S.server_build[c])) return 0;
  let power = getServerPowerScore();
  power += S.gpu_boost_level * 18 + S.cache_level * 9;
  if (power <= 0) return 0;
  const roll = Math.random();
  const baseChance = Math.min(0.94, 0.18 + power / 1800 + S.server_mining_level * 0.08 + S.mining_efficiency * 0.06);
  if (roll > baseChance) return 0;
  const floor = 1 + S.server_mining_level + S.mining_efficiency;
  const ceiling = Math.max(2, Math.trunc(power / 22) + S.server_mining_level + S.mining_efficiency + S.gpu_boost_level);
  const reward = rand(floor, ceiling);
  return Math.max(1, Math.round(reward * (1 + S.core_level * 0.01)));
}

/* =========================================================
   MILESTONES
   ========================================================= */
function checkMilestones() {
  const unlockedNow = [];
  for (const m of MILESTONE_THRESHOLDS) {
    if (S.click_count >= m && !S.milestones_unlocked.includes(m)) {
      S.milestones_unlocked.push(m);
      unlockedNow.push(m);
    }
  }
  for (const m of unlockedNow) showAchievement(m);
  if (unlockedNow.length) saveProgress();
}

/* =========================================================
   TOASTS
   ========================================================= */
const toastRoot = document.getElementById('toast-root');
function showToast(titleText, bodyText, colorClass) {
  const existing = toastRoot.querySelector('.toast');
  if (existing) existing.remove();
  const toast = el('div', 'toast');
  const title = el('div', 'toast-title', titleText);
  if (colorClass) title.style.color = colorClass;
  const body = el('div', 'toast-body', bodyText);
  toast.appendChild(title);
  toast.appendChild(body);
  toastRoot.appendChild(toast);
  requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 450);
  }, 4000);
}
function showAchievement(milestone) {
  showToast('ACHIEVEMENT', `${formatNumber(milestone)} clicks\n${MILESTONE_MESSAGES[milestone] || 'you did it'}`);
}
function showWelcomeBack(gain) {
  showToast('WELCOME BACK', `+${formatNumber(gain)} clicks\nearned while you were away`, '#98f2bf');
}

/* =========================================================
   CORE CLICK / TICK LOOP
   ========================================================= */
const clickLabel = document.getElementById('click-label');
const rankBadge = document.getElementById('rank-badge');
const clickButton = document.getElementById('click-button');

function refreshClickLabel() {
  clickLabel.textContent = `clicks : ${formatNumber(S.click_count)}`;
  bump(clickLabel, 'pulse');
  if (activeModalRefresh) activeModalRefresh();
}

let lastRankIndex = -1;
function updateRankProgress() {
  if (S.click_count > S.highest_click_count) S.highest_click_count = S.click_count;
  const idx = getRankIndex();
  rankBadge.textContent = getRankName();
  if (lastRankIndex === -1) {
    lastRankIndex = idx;
  } else if (idx > lastRankIndex) {
    lastRankIndex = idx;
    bump(rankBadge, 'rank-up');
    playUiSound('rank');
    showToast('RANK UP', `You are now ${getRankName()}`, '#ebc759');
  }
}

function showClickFeedback(amount) {
  if (amount <= 0) return;
  const rect = clickButton.getBoundingClientRect();
  const offsetX = (Math.random() * 60) - 30;
  const popup = el('div', 'float-popup', `+${formatNumber(amount)}`);
  const startX = rect.left + rect.width / 2 - 40 + offsetX;
  const startY = rect.top - 40;
  popup.style.left = `${startX}px`;
  popup.style.top = `${startY}px`;
  document.body.appendChild(popup);
  requestAnimationFrame(() => {
    popup.style.opacity = '1';
    popup.style.transform = 'translateY(-90px) scale(1.05)';
  });
  setTimeout(() => { popup.style.opacity = '0'; }, 420);
  setTimeout(() => popup.remove(), 820);
}

function onClick() {
  primeAudioOnce();
  const comboMult = getComboMultiplier();
  const tapGain = Math.trunc(S.clicks_per_tap * comboMult * getRankMultiplier()) + getExtraClickGain();
  S.click_count += tapGain;
  refreshClickLabel();
  updateRankProgress();
  checkMilestones();
  showClickFeedback(tapGain);
  playUiSound('tap');
  scheduleSave();

  clickButton.classList.remove('pop');
  void clickButton.offsetWidth;
  clickButton.classList.add('pop');
}
clickButton.addEventListener('click', onClick);

function addAutoClicks() {
  S.total_playtime_seconds += 1;
  const rankMult = getRankMultiplier();
  let changed = false;
  if (S.auto_click_rate > 0) {
    S.click_count += Math.trunc((S.auto_click_rate + getExtraClickGain()) * rankMult);
    changed = true;
  }
  const miningGain = getServerMiningReward();
  if (miningGain > 0) {
    S.click_count += Math.trunc(miningGain * rankMult);
    changed = true;
  }
  if (changed) {
    refreshClickLabel();
    updateRankProgress();
    checkMilestones();
    scheduleSave();
  }
}

let audioPrimed = false;
function primeAudioOnce() {
  if (audioPrimed) return;
  audioPrimed = true;
  if (S.music_enabled) playMusicTrack(musicTrackIndex);
}

/* =========================================================
   HACKED EVENT + HACK BATTLE
   Hacked events used to be a small dice-roll on every single tap and
   every 1-second tick, which meant frantic tapping (or an idle,
   ticking server) could trigger a flood of them in quick succession,
   or none for ages. That's replaced with a real scheduler: while a
   compatible server is online and the game is in the foreground, the
   game queues the next hacked event at a randomised time that
   averages out to about 3 events per 10 minutes of active play -
   never tied to how fast you're tapping.
   ========================================================= */
const hackedOverlay = document.getElementById('hacked-overlay');
const hackedText = document.getElementById('hacked-text');
const battleOverlay = document.getElementById('battle-overlay');
const battleTarget = document.getElementById('battle-target');
const battleStatus = document.getElementById('battle-status');
const battleTapTarget = document.getElementById('battle-tap-target');

let hackedEventActive = false;
let hackBattleActive = false;
let hackBattleTargetVal = 0;
let hackBattleProgress = 0;
let hackStealInterval = null;

const HACK_EVENT_AVG_INTERVAL_MS = (10 * 60 * 1000) / 3; // ~3 events per 10 minutes on average
let hackEventTimer = null;

function clearHackEventTimer() {
  if (hackEventTimer) { clearTimeout(hackEventTimer); hackEventTimer = null; }
}
function scheduleNextHackEvent() {
  clearHackEventTimer();
  if (!S.server_online || !isServerBuildCompatible() || document.hidden) return;
  const jitter = 0.6 + Math.random() * 0.8; // 0.6x - 1.4x of the average, so it's not perfectly metronomic
  const delay = HACK_EVENT_AVG_INTERVAL_MS * jitter;
  hackEventTimer = setTimeout(() => {
    hackEventTimer = null;
    triggerHackedEvent();
    scheduleNextHackEvent();
  }, delay);
}

function triggerHackedEvent() {
  if (!S.server_online || !isServerBuildCompatible()) return;
  if (hackedEventActive || hackBattleActive) return;
  hackedEventActive = true;
  playUiSound('server');

  hackedText.textContent = '';
  hackedOverlay.classList.remove('hidden');
  requestAnimationFrame(() => requestAnimationFrame(() => hackedOverlay.classList.add('show')));

  const message = 'HACKED';
  const glitchChars = ['#', '@', 'H', 'A', 'C', 'K', 'E', 'D', '0', '1'];
  message.split('').forEach((char, index) => {
    setTimeout(() => {
      let text = '';
      for (let i = 0; i < message.length; i++) {
        if (i < index) text += message[i];
        else if (i === index) text += char;
        else text += glitchChars[rand(0, glitchChars.length - 1)];
      }
      if (Math.random() < 0.35) {
        const gi = rand(0, message.length - 1);
        const arr = text.split('');
        arr[gi] = glitchChars[rand(0, glitchChars.length - 1)];
        text = arr.join('');
      }
      hackedText.textContent = text;
      if (index === message.length - 1) hackedText.textContent = message;
    }, 50 * index);
  });

  setTimeout(() => {
    hackedOverlay.classList.remove('show');
    hackedEventActive = false;
    setTimeout(() => {
      hackedOverlay.classList.add('hidden');
      startHackBattle();
    }, 350);
  }, 1700);
}

function startHackBattle() {
  if (hackBattleActive) return;
  hackBattleTargetVal = rand(200, 500);
  hackBattleProgress = 0;
  hackBattleActive = true;
  battleTarget.innerHTML = `CLICK ${hackBattleTargetVal} MORE<br/>TO FIGHT BACK`;
  battleStatus.textContent = 'Hackers are stealing your clicks...';
  battleOverlay.classList.remove('hidden');
  requestAnimationFrame(() => requestAnimationFrame(() => battleOverlay.classList.add('show')));

  if (hackStealInterval) clearInterval(hackStealInterval);
  hackStealInterval = setInterval(() => {
    if (!hackBattleActive) { clearInterval(hackStealInterval); hackStealInterval = null; return; }
    const stolen = Math.max(0, rand(25, 150) - getHackStealReduction());
    S.click_count = Math.max(0, S.click_count - stolen);
    refreshClickLabel();
    battleStatus.textContent = stolen > 0 ? `Hackers stole ${stolen} clicks!` : 'Network Defense blocked the theft!';
    saveProgress();
  }, 1000);
}

function attackHacker() {
  if (!hackBattleActive) return;
  const attackPower = getHackAttackPower();
  hackBattleProgress += attackPower;
  const remaining = Math.max(hackBattleTargetVal - hackBattleProgress, 0);
  battleTarget.innerHTML = `CLICK ${remaining} MORE<br/>TO FIGHT BACK`;
  battleStatus.textContent = `Fighting back... ${hackBattleProgress}/${hackBattleTargetVal} (x${attackPower})`;
  bump(battleTapTarget.parentElement.querySelector('.battle-banner'), 'battle-hit');

  if (hackBattleProgress >= hackBattleTargetVal) {
    hackBattleActive = false;
    if (hackStealInterval) { clearInterval(hackStealInterval); hackStealInterval = null; }
    S.click_count += rand(200, 900);
    refreshClickLabel();
    updateRankProgress();
    S.hack_battles_won += 1;
    battleStatus.textContent = 'Attack blocked. You held the line.';
    playUiSound('upgrade');
    checkMilestones();
    saveProgress();
    battleOverlay.classList.remove('show');
    setTimeout(() => battleOverlay.classList.add('hidden'), 350);
  }
}
battleTapTarget.addEventListener('click', attackHacker);

/* =========================================================
   MODAL SYSTEM
   ========================================================= */
const modalRoot = document.getElementById('modal-root');
const modalBackdrop = document.getElementById('modal-backdrop');
const modalBox = document.getElementById('modal-box');

// When a modal exposes a live-refresh hook (e.g. Upgrades), it's
// stored here so background ticks/taps can keep it in sync without
// forcing the modal to close and reopen.
let activeModalRefresh = null;

function openModal(buildFn, { full = false } = {}) {
  modalBox.innerHTML = '';
  modalBox.classList.toggle('full', full);
  buildFn(modalBox);
  modalRoot.classList.remove('hidden');
  requestAnimationFrame(() => requestAnimationFrame(() => modalRoot.classList.add('show')));
}
function closeModal() {
  modalRoot.classList.remove('show');
  activeModalRefresh = null;
  setTimeout(() => {
    modalRoot.classList.add('hidden');
    modalBox.innerHTML = '';
  }, 260);
}
modalBackdrop.addEventListener('click', closeModal);

function makeMenuButton(text, onClick, danger = false) {
  const btn = el('button', `menu-btn${danger ? ' danger' : ''}`, text);
  btn.addEventListener('click', onClick);
  return btn;
}
function makeCloseButton(onClick = closeModal) {
  const btn = el('button', 'close-btn', 'CLOSE');
  btn.addEventListener('click', onClick);
  return btn;
}

/* ---------- Settings ---------- */
function showSettingsMenu() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'Settings'));
    const soundBtn = makeMenuButton(`Sound: ${S.sound_enabled ? 'ON' : 'OFF'}`, () => {
      S.sound_enabled = !S.sound_enabled;
      soundBtn.textContent = `Sound: ${S.sound_enabled ? 'ON' : 'OFF'}`;
      saveProgress();
    });
    const musicBtn = makeMenuButton(`Music: ${S.music_enabled ? 'ON' : 'OFF'}`, () => {
      toggleMusic(!S.music_enabled);
      musicBtn.textContent = `Music: ${S.music_enabled ? 'ON' : 'OFF'}`;
    });
    box.appendChild(soundBtn);
    box.appendChild(musicBtn);
    box.appendChild(makeMenuButton('Reset Save', showResetConfirmation, true));
    box.appendChild(makeMenuButton('Guide', showGuide));
    box.appendChild(makeMenuButton('Credits', showCredits));
    box.appendChild(makeCloseButton());
  });
}

function showResetConfirmation() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'Confirm'));
    box.appendChild(el('p', null, 'Reset your save?'));
    box.appendChild(makeMenuButton('Yes', showFinalResetConfirmation, true));
    box.appendChild(makeMenuButton('No', closeModal));
  });
}
function showFinalResetConfirmation() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'Final check'));
    box.appendChild(el('p', null, 'This will erase all progress.\nAre you absolutely sure?'));
    box.appendChild(makeMenuButton('Yes, reset', () => { resetGameSave(); closeModal(); }, true));
    box.appendChild(makeMenuButton('Cancel', closeModal));
  });
}
function resetGameSave() {
  const keepSettings = { sound_enabled: S.sound_enabled, music_enabled: S.music_enabled };
  S = defaultState();
  Object.assign(S, keepSettings);
  recomputeStats();
  lastRankIndex = getRankIndex();
  clearHackEventTimer();
  refreshClickLabel();
  updateRankProgress();
  playUiSound('reset');
  saveProgress();
}

function showGuide() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'Guide'));
    const scroll = el('div', 'modal-scroll');
    const text = el('div', 'guide-text');
    text.innerHTML =
      '<b>The basics</b>\n' +
      'Tap the button to earn clicks. Spend clicks on UPGRADES to raise how much each tap and auto-click earns.\n\n' +
      '<b>Every upgrade does its own thing</b>\n' +
      'Each upgrade in the shop boosts its own stat and only that stat, shown live under its name - buying one never eats into another. Core Overclock is the one exception: it openly boosts everything a little, as a shared global multiplier.\n\n' +
      '<b>Rank</b>\n' +
      'Your rank (top of screen) rises with your all-time clicks and never goes down, even after you spend. Higher rank = a permanent bonus to every click. Tap it to see progress.\n\n' +
      "<b>Server & hacks - read this one</b>\n" +
      "Building and booting a server (SERVER tab) boosts your income, but once it's online and compatible, hackers will strike roughly 3 times every 10 minutes you're actively playing - it's on a timer, not random bad luck from clicking. Network Defense upgrades soften the damage and boost your counterattack.\n\n" +
      '<b>Other tips</b>\n' +
      '- MILESTONE shows every click goal and its message.\n' +
      "- Closing the app is safe - you'll get an offline bonus based on time away when you come back.";
    scroll.appendChild(text);
    box.appendChild(scroll);
    box.appendChild(makeCloseButton());
  });
}

function showCredits() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'Credits'));
    box.appendChild(el('p', null, 'Made by Iwodv'));
    box.appendChild(makeCloseButton());
  });
}

/* ---------- Rank info ---------- */
function showRankInfo() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'RANK'));
    box.appendChild(el('p', null, `Rank: ${getRankName()}`)).style.color = '#ebc759';
    const bonusPct = Math.round((getRankMultiplier() - 1) * 100);
    const bonus = el('p', null, `+${bonusPct}% clicks from rank`);
    bonus.style.color = '#62e0a6';
    box.appendChild(bonus);
    const remaining = getNextRankRequirement();
    let statusText;
    if (remaining === null) {
      statusText = 'Top rank reached - Obsidian V at 150M clicks';
    } else {
      const nextName = RANK_TIERS[getRankIndex() + 1];
      statusText = `${formatNumber(remaining)} more all-time clicks to rise to ${nextName}`;
    }
    box.appendChild(el('p', null, statusText));
    box.appendChild(makeCloseButton());
  });
}
rankBadge.addEventListener('click', showRankInfo);
document.getElementById('settings-btn').addEventListener('click', showSettingsMenu);

/* ---------- Milestones ---------- */
function showMilestones() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'MILESTONES'));
    box.appendChild(el('div', 'modal-divider'));
    const scroll = el('div', 'modal-scroll');
    for (const m of MILESTONE_THRESHOLDS) {
      const row = el('div', 'ms-row');
      row.appendChild(el('div', 'ms-value', formatNumber(m)));
      const barWrap = el('div', 'ms-bar-wrap');
      const done = S.click_count >= m;
      const pct = done ? 100 : Math.min((S.click_count / m) * 100, 100);
      const fill = el('div', `ms-bar-fill${done ? ' done' : ''}`);
      barWrap.appendChild(fill);
      row.appendChild(barWrap);
      row.appendChild(el('div', 'ms-percent', `${Math.round(pct)}%`));
      scroll.appendChild(row);
      // set width after insertion so the fill animates in smoothly
      requestAnimationFrame(() => { fill.style.width = `${pct}%`; });
    }
    box.appendChild(scroll);
    box.appendChild(makeCloseButton());
  });
}
document.getElementById('milestone-btn').addEventListener('click', showMilestones);

/* ---------- Upgrades ---------- */
function showUpgrades() {
  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'UPGRADES'));
    const summary = el('div', 'upgrade-summary');
    box.appendChild(summary);
    box.appendChild(el('div', 'modal-divider'));
    const scroll = el('div', 'modal-scroll');
    box.appendChild(scroll);
    box.appendChild(makeCloseButton());

    const rowRefreshers = [];

    function renderSummary() {
      summary.innerHTML = '';
      const stats = [
        ['Click Power', `${formatNumber(getClicksPerTap())}/tap`],
        ['Auto Clicker', `${formatNumber(getAutoClickRate())}/sec`],
        ['Global Boost', `x${(1 + S.core_level * 0.01).toFixed(2)}`],
      ];
      for (const [label, value] of stats) {
        const item = el('div', 'summary-item');
        item.appendChild(el('div', 'summary-label', label));
        item.appendChild(el('div', 'summary-value', value));
        summary.appendChild(item);
      }
    }

    function renderRow(upgrade) {
      const row = el('div', 'up-row');
      const info = el('div', 'up-info');
      const nameEl = el('div', 'up-name', upgrade.name);
      const effectEl = el('div', 'up-effect');
      const costEl = el('div', 'up-cost');
      info.appendChild(nameEl);
      info.appendChild(effectEl);
      info.appendChild(costEl);
      row.appendChild(info);
      const buyBtn = el('button', 'up-buy', 'BUY');
      row.appendChild(buyBtn);
      scroll.appendChild(row);

      function refreshRow() {
        const level = S[upgrade.levelKey];
        const cost = upgrade.cost();
        costEl.textContent = `Lvl ${level} • ${formatNumber(cost)} clicks`;
        effectEl.textContent = upgrade.effect();
        buyBtn.disabled = S.click_count < cost;
      }

      buyBtn.addEventListener('click', () => {
        const ok = buyUpgrade(upgrade.kind);
        if (ok) {
          bump(row, 'flash-buy');
          playUiSound('upgrade');
          renderSummary();
          for (const refresh of rowRefreshers) refresh();
        } else {
          bump(row, 'flash-deny');
          playUiSound('deny');
        }
      });

      refreshRow();
      rowRefreshers.push(refreshRow);
    }

    for (const upgrade of UPGRADE_ROWS) renderRow(upgrade);
    renderSummary();

    activeModalRefresh = () => {
      renderSummary();
      for (const refresh of rowRefreshers) refresh();
    };
  });
}
document.getElementById('upgrades-btn').addEventListener('click', showUpgrades);

/* ---------- Server builder ---------- */
function showServerBuilder() {
  let selectedCategory = 'CPU';

  openModal((box) => {
    box.appendChild(el('div', 'modal-title', 'SERVER BUILDER'));

    const power = el('div', 'server-summary', `Power Score: ${getServerPowerScore()}`);
    const status = el('div', 'server-status', getServerStatusText());
    box.appendChild(power);
    box.appendChild(status);

    const bootBtn = el('button', 'boot-btn', S.server_online ? 'SHUTDOWN SERVER' : 'BOOT SERVER');
    function refreshBootBtn() {
      const compatible = isServerBuildCompatible();
      bootBtn.disabled = !compatible;
      bootBtn.textContent = compatible ? (S.server_online ? 'SHUTDOWN SERVER' : 'BOOT SERVER') : 'BUILD INCOMPLETE';
    }
    bootBtn.addEventListener('click', () => {
      if (!isServerBuildCompatible()) return;
      S.server_online = !S.server_online;
      playUiSound('server');
      if (S.server_online) scheduleNextHackEvent(); else clearHackEventTimer();
      saveProgress();
      refreshBootBtn();
      bump(bootBtn, 'boot-flash');
    });
    refreshBootBtn();
    box.appendChild(bootBtn);

    const treeWrap = el('div', 'tree-wrap');
    box.appendChild(treeWrap);

    const catalogHeader = el('div', 'catalog-header');
    const scroll = el('div', 'modal-scroll');
    const catalog = el('div');
    scroll.appendChild(catalog);
    box.appendChild(catalogHeader);
    box.appendChild(scroll);
    box.appendChild(makeCloseButton());

    function partDetails(cat, part) {
      switch (cat) {
        case 'CPU': return `${part.name} | ${part.socket} | ${part.tdp}W`;
        case 'Motherboard': return `${part.name} | ${part.socket} | ${part.memory_generation} | ${part.form_factor}`;
        case 'RAM': return `${part.name} | ${part.generation} | ${part.speed}MHz`;
        case 'GPU': return `${part.name} | ${part.vram}GB | ${part.power_draw}W`;
        case 'PSU': return `${part.name} | ${part.watts}W`;
        case 'Case': return `${part.name} | ${part.gpu_max_length}mm GPU`;
        default: return part.name;
      }
    }

    function refreshCatalog() {
      catalog.innerHTML = '';
      catalogHeader.textContent = `${selectedCategory} PARTS`;
      for (const part of SERVER_PARTS[selectedCategory]) {
        const owned = S.server_build[selectedCategory] === part;
        const row = el('button', `part-row${owned ? ' owned' : ''}`);
        row.innerHTML = `${partDetails(selectedCategory, part)}<br/>${formatNumber(part.cost)} clicks`;
        row.addEventListener('click', () => {
          if (S.click_count < part.cost) {
            status.textContent = `Need ${formatNumber(part.cost - S.click_count)} more clicks`;
            bump(row, 'flash-deny');
            playUiSound('deny');
            return;
          }
          S.click_count -= part.cost;
          S.server_build[selectedCategory] = part;
          refreshClickLabel();
          saveProgress();
          status.textContent = getServerStatusText();
          power.textContent = `Power Score: ${getServerPowerScore()}`;
          refreshBootBtn();
          playUiSound('upgrade');
          refreshTree();
          refreshCatalog();
        });
        catalog.appendChild(row);
      }
    }

    function refreshTree() {
      treeWrap.innerHTML = '';
      const w = treeWrap.clientWidth || 300;
      const h = treeWrap.clientHeight || 230;
      const centerX = w * 0.5, centerY = h * 0.5;

      // connecting lines from motherboard center to each slot
      for (const cat of Object.keys(TREE_POSITIONS)) {
        const pos = TREE_POSITIONS[cat];
        const tx = w * pos.x, ty = h * pos.y;
        const dx = tx - centerX, dy = ty - centerY;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx) * (180 / Math.PI);
        const line = el('div', 'tree-line');
        line.style.width = `${length}px`;
        line.style.left = `${centerX}px`;
        line.style.top = `${centerY}px`;
        line.style.transform = `rotate(${angle}deg)`;
        treeWrap.appendChild(line);
      }

      // motherboard center slot
      const moboPart = S.server_build.Motherboard;
      const moboSlot = el('button', `tree-slot motherboard${moboPart ? ' filled' : ''}${selectedCategory === 'Motherboard' ? ' selected' : ''}`, moboPart ? moboPart.name : 'Motherboard');
      moboSlot.style.left = `${centerX}px`;
      moboSlot.style.top = `${centerY}px`;
      moboSlot.addEventListener('click', () => { selectedCategory = 'Motherboard'; refreshTree(); refreshCatalog(); });
      treeWrap.appendChild(moboSlot);

      for (const cat of Object.keys(TREE_POSITIONS)) {
        const pos = TREE_POSITIONS[cat];
        const part = S.server_build[cat];
        const slot = el('button', `tree-slot${part ? ' filled' : ''}${selectedCategory === cat ? ' selected' : ''}`, (part ? part.name : cat).slice(0, 16));
        slot.style.left = `${w * pos.x}px`;
        slot.style.top = `${h * pos.y}px`;
        slot.addEventListener('click', () => { selectedCategory = cat; refreshTree(); refreshCatalog(); });
        treeWrap.appendChild(slot);
      }
    }

    refreshTree();
    refreshCatalog();
  }, { full: true });
}
document.getElementById('server-btn').addEventListener('click', showServerBuilder);

/* =========================================================
   INTRO SCREEN -> GAME SCREEN
   ========================================================= */
function runIntro() {
  const introScreen = document.getElementById('intro-screen');
  const gameScreen = document.getElementById('game-screen');
  const introTitle = document.getElementById('intro-title');
  const introLoadingLabel = document.getElementById('intro-loading-label');
  const loadingFill = document.getElementById('loading-fill');

  requestAnimationFrame(() => {
    introTitle.style.opacity = '1';
    introLoadingLabel.style.opacity = '1';
    loadingFill.style.width = '100%';
  });

  setTimeout(() => {
    introScreen.classList.add('fade-out');
    setTimeout(() => {
      introScreen.classList.add('hidden');
      gameScreen.classList.remove('hidden');
      requestAnimationFrame(() => gameScreen.classList.add('show'));
      if (S.offline_bonus_total > 0) {
        setTimeout(() => showWelcomeBack(S.offline_bonus_total), 500);
      }
    }, 400);
  }, 1900);
}

/* =========================================================
   BOOT
   ========================================================= */
function boot() {
  loadProgress();
  lastRankIndex = getRankIndex();
  refreshClickLabel();
  updateRankProgress();
  setInterval(addAutoClicks, 1000);
  scheduleNextHackEvent();
  runIntro();

  // Any first tap anywhere primes the audio context / music (mobile
  // browsers/webviews block autoplay until a user gesture happens).
  document.body.addEventListener('pointerdown', primeAudioOnce, { once: true });

  // Pause the hack-event scheduler while backgrounded and resume it
  // (with a fresh randomised delay) when the app comes back to the
  // foreground; also flush any pending throttled save immediately so
  // backgrounding/closing never loses progress.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearHackEventTimer();
      saveProgress();
    } else {
      scheduleNextHackEvent();
    }
  });
  window.addEventListener('pagehide', saveProgress);
}

document.addEventListener('DOMContentLoaded', boot);
