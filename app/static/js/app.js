let chartInstance = null;
let mapInstance = null;
let searchMarker = null;
let radiusCircle = null;
let stationMarkersLayer = null;
let mapReady = false;
let currentStations = [];
let selectedStationId = null;
let latestAnalysis = null;

const analysisCache = new Map();
const availabilityCache = new Map();

const radiusInput = document.getElementById('radius');
const radiusValue = document.getElementById('radiusValue');
const statusElement = document.getElementById('status');
const searchButton = document.getElementById('searchBtn');
const heroSection = document.getElementById('heroSection');
const workspaceSection = document.getElementById('workspaceSection');
const searchCard = document.getElementById('searchCard');
const searchDock = document.getElementById('searchDock');
const mapSummary = document.getElementById('mapSummary');
const chartPanel = document.getElementById('chartPanel');
const tablePanel = document.getElementById('tablePanel');
const chartTabBtn = document.getElementById('chartTabBtn');
const tableTabBtn = document.getElementById('tableTabBtn');
const stationList = document.getElementById('stationList');
const tableWrapper = document.getElementById('tableWrapper');
const ruleElement = document.getElementById('rule');

const METRIC_KEYS = [
  'tmin', 'tmax',
  'spring_tmin', 'spring_tmax',
  'summer_tmin', 'summer_tmax',
  'autumn_tmin', 'autumn_tmax',
  'winter_tmin', 'winter_tmax',
];

const SERIES_CONFIG = {
  tmin: { label: 'TMIN · Alle', color: '#68cfff' },
  spring_tmin: { label: 'TMIN · Frühling', color: '#2e7d32' },
  summer_tmin: { label: 'TMIN · Sommer', color: '#b8860b' },
  autumn_tmin: { label: 'TMIN · Herbst', color: '#6d4c41' },
  winter_tmin: { label: 'TMIN · Winter', color: '#6b7280' },
  tmax: { label: 'TMAX · Alle', color: '#ff6d8d' },
  spring_tmax: { label: 'TMAX · Frühling', color: '#7ed957' },
  summer_tmax: { label: 'TMAX · Sommer', color: '#ffd54f' },
  autumn_tmax: { label: 'TMAX · Herbst', color: '#a47551' },
  winter_tmax: { label: 'TMAX · Winter', color: '#c4c9d1' },
};

function getInput(id) {
  return document.getElementById(id);
}

function getValue(id) {
  return getInput(id).value;
}

function normalizeDecimalInput(id) {
  const input = getInput(id);
  if (!input) return '';
  const normalized = String(input.value ?? '').replace(/\./g, ',').replace(/\s+/g, '').trim();
  input.value = normalized;
  return normalized;
}

function formatGermanDecimal(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value ?? '');
  return new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(number);
}

function formatGermanOptional(value, digits = 1) {
  if (value === null || value === undefined) return '—';
  return formatGermanDecimal(value, digits);
}

function formatDistanceKm(value) {
  return `${formatGermanDecimal(value, 2)} km`;
}

function clearFieldErrors() {
  document.querySelectorAll('input.invalid').forEach((element) => {
    element.classList.remove('invalid');
    element.removeAttribute('aria-invalid');
  });
}

function markFieldError(id) {
  const input = getInput(id);
  if (!input) return;
  input.classList.add('invalid');
  input.setAttribute('aria-invalid', 'true');
}

function parseStrictDecimal(id, label, min, max) {
  const raw = normalizeDecimalInput(id);
  if (!raw) throw new Error(`${label} darf nicht leer sein.`);
  if (!/^-?\d+(,\d+)?$/.test(raw)) {
    throw new Error(`${label} muss eine Zahl im Format 12,3 sein.`);
  }
  const value = Number(raw.replace(',', '.'));
  if (!Number.isFinite(value) || value < min || value > max) {
    throw new Error(`${label} muss zwischen ${min} und ${max} liegen.`);
  }
  return value;
}

function parseStrictInteger(id, label, min, max) {
  const input = getInput(id);
  const raw = String(input.value ?? '').trim();
  if (!raw) throw new Error(`${label} darf nicht leer sein.`);
  if (!/^\d+$/.test(raw)) throw new Error(`${label} muss eine ganze Zahl sein.`);
  const value = Number(raw);
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(`${label} muss zwischen ${min} und ${max} liegen.`);
  }
  input.value = String(value);
  return value;
}

function validateSearchInputs() {
  clearFieldErrors();
  try {
    const latitude = parseStrictDecimal('latitude', 'Breitengrad', -90, 90);
    const longitude = parseStrictDecimal('longitude', 'Längengrad', -180, 180);
    const radiusKm = parseStrictInteger('radius', 'Suchradius', 1, 100);
    const limit = parseStrictInteger('limit', 'Max. Stationen', 1, 25);
    const startYear = parseStrictInteger('startYear', 'Startjahr', 1700, 2026);
    const endYear = parseStrictInteger('endYear', 'Endjahr', 1700, 2026);

    if (startYear > endYear) {
      markFieldError('startYear');
      markFieldError('endYear');
      throw new Error('Startjahr darf nicht größer als Endjahr sein.');
    }

    return { latitude, longitude, radiusKm, limit, startYear, endYear };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes('Breitengrad')) markFieldError('latitude');
    if (message.includes('Längengrad')) markFieldError('longitude');
    if (message.includes('Suchradius')) markFieldError('radius');
    if (message.includes('Max. Stationen')) markFieldError('limit');
    if (message.includes('Startjahr')) markFieldError('startYear');
    if (message.includes('Endjahr')) markFieldError('endYear');
    throw new Error(message || 'Ungültige Eingabe.');
  }
}

function getSelectedSeriesKeys() {
  return Array.from(document.querySelectorAll('[data-series-key]:checked')).map((input) => input.dataset.seriesKey);
}

function setStatus(message, isError = false) {
  statusElement.textContent = typeof message === 'string' ? message : 'Unbekannter Fehler';
  statusElement.classList.toggle('error', isError);
}

function setBusy(isBusy) {
  searchButton.disabled = isBusy;
  searchButton.textContent = isBusy ? 'Suche läuft…' : 'Stationen suchen';
}

function extractErrorMessage(payload) {
  if (typeof payload === 'string') return payload;
  if (Array.isArray(payload)) {
    return payload.map((item) => extractErrorMessage(item)).filter(Boolean).join(' · ');
  }
  if (payload && typeof payload === 'object') {
    if (typeof payload.detail === 'string') return payload.detail;
    if (Array.isArray(payload.detail)) return extractErrorMessage(payload.detail);
    if (payload.detail && typeof payload.detail === 'object') return extractErrorMessage(payload.detail);
    if (typeof payload.msg === 'string') return payload.msg;
    if (Array.isArray(payload.loc) && typeof payload.msg === 'string') {
      return `${payload.loc.join(' › ')}: ${payload.msg}`;
    }
  }
  return '';
}

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = extractErrorMessage(data) || 'Unbekannter Fehler';
    throw new Error(message);
  }
  return data;
}

function syncRadiusLabel() {
  const min = Number(radiusInput.min || 0);
  const max = Number(radiusInput.max || 100);
  const value = Number(radiusInput.value);
  const percent = ((value - min) / (max - min)) * 100;
  radiusValue.textContent = formatGermanDecimal(value, 0);
  radiusInput.style.background = `linear-gradient(to right, #39c6ff 0%, #39c6ff ${percent}%, #4a556d ${percent}%, #4a556d 100%)`;
  if (radiusCircle) radiusCircle.setRadius(value * 1000);
}

function activateTab(tab) {
  const isChart = tab === 'chart';
  chartTabBtn.classList.toggle('active', isChart);
  tableTabBtn.classList.toggle('active', !isChart);
  chartPanel.classList.toggle('active', isChart);
  tablePanel.classList.toggle('active', !isChart);
  if (isChart && chartInstance) {
    setTimeout(() => chartInstance.resize(), 50);
  }
}

function ensureWorkspaceMode() {
  if (!workspaceSection.classList.contains('hidden')) return;
  searchDock.appendChild(searchCard);
  searchCard.classList.add('compact');
  heroSection.classList.add('hidden');
  workspaceSection.classList.remove('hidden');
}

function initMap() {
  if (mapReady) return;
  mapInstance = L.map('map', { zoomControl: true, scrollWheelZoom: true }).setView([20, 0], 2);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '&copy; OpenStreetMap &copy; CARTO',
  }).addTo(mapInstance);
  stationMarkersLayer = L.layerGroup().addTo(mapInstance);
  mapReady = true;
  invalidateMap();
}

function invalidateMap() {
  if (!mapInstance) return;
  requestAnimationFrame(() => {
    mapInstance.invalidateSize(true);
    setTimeout(() => mapInstance.invalidateSize(true), 120);
    setTimeout(() => mapInstance.invalidateSize(true), 320);
  });
}

window.addEventListener('resize', invalidateMap);

function pointIcon() {
  return L.divIcon({ className: '', html: '<div class="map-point-marker"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });
}

function stationIcon(isActive = false) {
  return L.divIcon({
    className: '',
    html: `<div class="map-station-marker${isActive ? ' active' : ''}"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

function buildPopupHtml(station) {
  return `
    <div class="map-popup-title">${station.name}</div>
    <div class="map-popup-meta">${station.id} · ${formatDistanceKm(station.distance_km)} · ${station.mindate}-${station.maxdate}</div>
    <button class="map-popup-button" data-station-popup-id="${station.id}">Diese Station auswerten</button>
  `;
}

function focusMapOnResults(latitude, longitude, stations) {
  if (!mapInstance) return;
  const bounds = [[latitude, longitude], ...stations.map((s) => [s.latitude, s.longitude])];
  if (bounds.length <= 1) {
    mapInstance.setView(bounds[0], 9);
    return;
  }
  mapInstance.fitBounds(bounds, { padding: [42, 42], maxZoom: 9 });
}

function updateMapSummary(count, activeName = '') {
  mapSummary.innerHTML = `
    <strong>${count} Station${count === 1 ? '' : 'en'} gefunden.</strong>
    <span>${activeName ? `${activeName} ist ausgewählt.` : 'Bitte wählen Sie eine Station aus.'}</span>
  `;
}

function updateMap(stations) {
  initMap();
  const { latitude, longitude, radiusKm } = validateSearchInputs();

  if (searchMarker) mapInstance.removeLayer(searchMarker);
  if (radiusCircle) mapInstance.removeLayer(radiusCircle);
  stationMarkersLayer.clearLayers();

  searchMarker = L.marker([latitude, longitude], { icon: pointIcon() }).addTo(mapInstance)
    .bindPopup('<div class="map-popup-title">Eingegebene Koordinaten</div><div class="map-popup-meta">Mittelpunkt der Suche</div>');

  radiusCircle = L.circle([latitude, longitude], {
    radius: radiusKm * 1000,
    color: '#d8e8ff',
    weight: 2,
    fillColor: '#39c6ff',
    fillOpacity: 0.08,
  }).addTo(mapInstance);

  stations.forEach((station) => {
    const marker = L.marker([station.latitude, station.longitude], {
      icon: stationIcon(station.id === selectedStationId),
      title: station.name,
    });
    marker.stationId = station.id;
    marker.bindPopup(buildPopupHtml(station));
    marker.on('click', () => analyzeStation(station.id));
    marker.on('popupopen', (event) => {
      const button = event.popup.getElement()?.querySelector('[data-station-popup-id]');
      if (button) button.addEventListener('click', () => analyzeStation(station.id));
    });
    stationMarkersLayer.addLayer(marker);
  });

  focusMapOnResults(latitude, longitude, stations);
  updateMapSummary(stations.length);
  invalidateMap();
}

function highlightStation(stationId, openPopup = true) {
  selectedStationId = stationId;
  document.querySelectorAll('.station-item').forEach((element) => {
    element.classList.toggle('active', element.dataset.stationId === stationId);
  });

  const station = currentStations.find((entry) => entry.id === stationId);
  updateMapSummary(currentStations.length, station?.name || '');

  if (!stationMarkersLayer) return;
  stationMarkersLayer.eachLayer((layer) => {
    const isActive = layer.stationId === stationId;
    layer.setIcon(stationIcon(isActive));
    if (isActive && openPopup) {
      layer.openPopup();
      mapInstance.panTo(layer.getLatLng(), { animate: true });
    }
  });
}

async function fetchAnalysis(stationId) {
  const cacheKey = `${stationId}-${getValue('startYear')}-${getValue('endYear')}`;
  if (analysisCache.has(cacheKey)) return analysisCache.get(cacheKey);

  const params = new URLSearchParams({
    start_year: getValue('startYear'),
    end_year: getValue('endYear'),
  });
  const response = await fetch(`/api/stations/${stationId}/analysis?${params.toString()}`);
  const data = await readJson(response);
  analysisCache.set(cacheKey, data);
  return data;
}

function calculateAvailability(analysis) {
  const points = analysis.values || [];
  const totalSlots = points.length * METRIC_KEYS.length;
  let filledSlots = 0;

  for (const point of points) {
    for (const key of METRIC_KEYS) {
      if (point[key] !== null && point[key] !== undefined) filledSlots += 1;
    }
  }

  const availableYears = points.filter((point) => point.has_data).length;
  const coverage = totalSlots ? Math.round((filledSlots / totalSlots) * 1000) / 10 : 0;
  return {
    coverage,
    availableYears,
    label: `${formatGermanDecimal(coverage, 1)} % gesamt verfügbar`,
  };
}

function patchStationAvailability(stationId, availability, isError = false) {
  const root = document.querySelector(`.station-item[data-station-id="${stationId}"]`);
  if (!root) return;
  const badge = root.querySelector('.station-availability');
  const yearsElement = root.querySelector('.station-years');
  if (badge) {
    badge.classList.remove('loading');
    badge.textContent = isError ? 'Nicht berechenbar' : availability.label;
  }
  if (yearsElement && !isError) {
    yearsElement.textContent = `${availability.availableYears} Jahre im gewählten Zeitraum auswertbar`;
  }
}

async function hydrateStationAvailability(stations) {
  for (const station of stations) {
    const cacheKey = `${station.id}-${getValue('startYear')}-${getValue('endYear')}`;
    if (availabilityCache.has(cacheKey)) {
      patchStationAvailability(station.id, availabilityCache.get(cacheKey));
      continue;
    }
    try {
      const analysis = await fetchAnalysis(station.id);
      const availability = calculateAvailability(analysis);
      availabilityCache.set(cacheKey, availability);
      patchStationAvailability(station.id, availability);
    } catch {
      patchStationAvailability(station.id, { label: 'Nicht berechenbar', availableYears: 0 }, true);
    }
  }
}

function renderStations(stations) {
  if (!stations.length) {
    stationList.innerHTML = '<p class="muted">Keine passenden Stationen gefunden.</p>';
    return;
  }

  stationList.innerHTML = stations.map((station) => `
    <article class="station-item" data-station-id="${station.id}">
      <div class="station-item-top">
        <div>
          <div class="station-name">${station.name}</div>
          <div class="station-meta">${formatDistanceKm(station.distance_km)} Entfernung · ${station.id}</div>
          <div class="station-submeta">Verfügbare Jahre: ${station.mindate}-${station.maxdate}</div>
          <div class="station-submeta station-years">Datenverfügbarkeit wird berechnet…</div>
        </div>
        <button type="button" data-action="analyze-station" data-station-id="${station.id}">Auswerten</button>
      </div>
      <div class="station-availability loading">Wird geladen…</div>
    </article>
  `).join('');

  hydrateStationAvailability(stations);
}

function clearAnalysis() {
  latestAnalysis = null;
  ruleElement.textContent = 'Wähle rechts eine Station aus oder klicke einen Marker auf der Karte an.';
  renderChart([], '');
  tableWrapper.innerHTML = '<p class="muted">Noch keine Station ausgewählt.</p>';
}

async function searchStations() {
  try {
    setBusy(true);
    const values = validateSearchInputs();
    setStatus('Suche läuft … NOAA-Stationsdaten werden gefiltert.');

    const params = new URLSearchParams({
      latitude: String(values.latitude),
      longitude: String(values.longitude),
      radius_km: String(values.radiusKm),
      limit: String(values.limit),
      start_year: String(values.startYear),
      end_year: String(values.endYear),
    });

    const response = await fetch(`/api/stations?${params.toString()}`);
    const data = await readJson(response);

    ensureWorkspaceMode();
    currentStations = data;
    selectedStationId = null;
    latestAnalysis = null;
    renderStations(data);
    updateMap(data);
    clearAnalysis();
    activateTab('chart');
    setStatus(`${data.length} Station(en) geladen.`);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Ungültige Eingabe.';
    setStatus(message, true);
  } finally {
    setBusy(false);
  }
}

function buildDatasets(values, stationId) {
  return getSelectedSeriesKeys().map((key) => ({
    label: `${SERIES_CONFIG[key].label} · ${stationId}`,
    data: values.map((item) => item[key]),
    spanGaps: false,
    borderColor: SERIES_CONFIG[key].color,
    backgroundColor: 'transparent',
    pointRadius: 2,
    pointHoverRadius: 4,
    borderWidth: 2,
    tension: 0.28,
  }));
}

function renderChart(values, stationId) {
  const ctx = document.getElementById('chart');
  if (chartInstance) chartInstance.destroy();

  if (!values.length || !getSelectedSeriesKeys().length) {
    chartInstance = null;
    const chartCtx = ctx.getContext('2d');
    chartCtx.clearRect(0, 0, ctx.width, ctx.height);
    return;
  }

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: values.map((item) => item.year),
      datasets: buildDatasets(values, stationId),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          onClick: (event) => {
            if (event?.native?.preventDefault) event.native.preventDefault();
            if (event?.native?.stopPropagation) event.native.stopPropagation();
            if (event?.native?.stopImmediatePropagation) event.native.stopImmediatePropagation();
            return;
          },
          onHover: null,
          onLeave: null,
          labels: {
            color: '#dce9ff',
            boxWidth: 14,
            usePointStyle: true,
            pointStyle: 'line',
          },
        },
      },
      scales: {
        x: { ticks: { color: '#9fb7db' }, grid: { color: 'rgba(159, 183, 219, 0.12)' } },
        y: {
          ticks: {
            color: '#9fb7db',
            callback: (value) => formatGermanOptional(value, 1),
          },
          grid: { color: 'rgba(159, 183, 219, 0.12)' },
        },
      },
    },
  });
}

function getFilteredRows(values) {
  const selectedKeys = getSelectedSeriesKeys();
  return values.filter((item) => selectedKeys.some((key) => item[key] !== null && item[key] !== undefined));
}

function renderTable(values, startYear, endYear) {
  const selectedKeys = getSelectedSeriesKeys();

  if (!selectedKeys.length) {
    tableWrapper.innerHTML = '<p class="muted">Bitte wähle mindestens einen Filter aus.</p>';
    return;
  }

  if (!values.length || !values.some((item) => selectedKeys.some((key) => item[key] !== null && item[key] !== undefined))) {
    tableWrapper.innerHTML = `<p class="muted">Für ${startYear} bis ${endYear} wurden für die aktuelle Filterauswahl keine NOAA-Daten gefunden.</p>`;
    return;
  }

  const columns = [
    { key: 'year', label: 'Jahr' },
    ...selectedKeys.map((key) => ({ key, label: SERIES_CONFIG[key].label })),
  ];

  const headerHtml = columns.map((column) => `<th>${column.label}</th>`).join('');
  const rows = values.map((item) => `
    <tr>
      ${columns.map((column) => `<td>${column.key === 'year' ? item.year : formatGermanOptional(item[column.key], 1)}</td>`).join('')}
    </tr>
  `).join('');

  tableWrapper.innerHTML = `
    <div class="table-scroll">
      <table>
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function rerenderAnalysis() {
  if (!latestAnalysis) return;
  const rows = latestAnalysis.values || [];
  renderChart(rows, latestAnalysis.station_id);
  renderTable(rows, latestAnalysis.start_year, latestAnalysis.end_year);
}

async function analyzeStation(stationId) {
  try {
    ensureWorkspaceMode();
    highlightStation(stationId, true);
    setStatus(`Analysiere ${stationId} …`);

    const data = await fetchAnalysis(stationId);
    latestAnalysis = {
      ...data,
      values: (data.values || []),
    };

    ruleElement.textContent = data.missing_data_rule;
    rerenderAnalysis();
    activateTab('chart');
    setStatus(`Analyse für ${stationId} abgeschlossen.`);

    const availability = calculateAvailability(data);
    const cacheKey = `${stationId}-${getValue('startYear')}-${getValue('endYear')}`;
    availabilityCache.set(cacheKey, availability);
    patchStationAvailability(stationId, availability);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Analyse konnte nicht geladen werden.';
    setStatus(message, true);
  }
}

radiusInput.addEventListener('input', syncRadiusLabel);
searchButton.addEventListener('click', searchStations);
chartTabBtn.addEventListener('click', () => activateTab('chart'));
tableTabBtn.addEventListener('click', () => activateTab('table'));

stationList.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action="analyze-station"]');
  if (button) {
    event.preventDefault();
    event.stopPropagation();
    analyzeStation(button.dataset.stationId);
    return;
  }
  const card = event.target.closest('.station-item');
  if (card) analyzeStation(card.dataset.stationId);
});

document.addEventListener('DOMContentLoaded', () => {
  ['latitude', 'longitude'].forEach((id) => {
    const input = getInput(id);
    input.addEventListener('input', () => {
      normalizeDecimalInput(id);
      input.classList.remove('invalid');
      input.removeAttribute('aria-invalid');
    });
    input.addEventListener('blur', () => normalizeDecimalInput(id));
  });

  ['radius', 'limit', 'startYear', 'endYear'].forEach((id) => {
    const input = getInput(id);
    input.addEventListener('input', () => {
      input.classList.remove('invalid');
      input.removeAttribute('aria-invalid');
    });
  });

  document.querySelectorAll('[data-series-key]').forEach((input) => {
    input.addEventListener('change', () => {
      if (!getSelectedSeriesKeys().length) input.checked = true;
      rerenderAnalysis();
    });
  });

  syncRadiusLabel();
  activateTab('chart');
  clearAnalysis();
});
