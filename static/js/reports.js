const appliances = [
    { name: "Air Conditioner", watts: 1500, hours: 3 },
    { name: "Refrigerator", watts: 200, hours: 8 },
    { name: "Television", watts: 100, hours: 5 },
    { name: "Electric Fan", watts: 75, hours: 8 },
    { name: "Laptop", watts: 65, hours: 6 }
];

const monthInput = document.getElementById("reportMonth");
const tariffInput = document.getElementById("tariff");
const tableBody = document.getElementById("applianceTable");

let usageChart = null;
let costChart = null;

const naira = new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 2
});

function getMonthDays() {
    const value = monthInput.value;

    if (!value) {
        return new Date().getDate();
    }

    const [year, month] = value.split("-").map(Number);
    return new Date(year, month, 0).getDate();
}

function getTariff() {
    const value = Number(tariffInput.value);
    return Number.isFinite(value) && value >= 0 ? value : 0;
}

function calculateAppliances() {
    const days = getMonthDays();
    const tariff = getTariff();

    return appliances.map((appliance) => {
        const watts = Math.max(0, Number(appliance.watts) || 0);
        const hours = Math.min(24, Math.max(0, Number(appliance.hours) || 0));
        const dailyKwh = watts * hours / 1000;
        const monthlyKwh = dailyKwh * days;

        return {
            ...appliance,
            watts,
            hours,
            dailyKwh,
            monthlyKwh,
            dailyCost: dailyKwh * tariff,
            monthlyCost: monthlyKwh * tariff
        };
    });
}

function renderTable(data) {
    tableBody.innerHTML = "";

    data.forEach((item, index) => {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>
                <input class="appliance-name" aria-label="Appliance name"
                    data-index="${index}" data-field="name"
                    value="${escapeHtml(item.name)}">
            </td>
            <td>
                <input type="number" aria-label="Power in watts"
                    min="0" step="1" data-index="${index}"
                    data-field="watts" value="${item.watts}">
            </td>
            <td>
                <input type="number" aria-label="Hours per day"
                    min="0" max="24" step="0.5" data-index="${index}"
                    data-field="hours" value="${item.hours}">
            </td>
            <td>${item.dailyKwh.toFixed(2)}</td>
            <td>${item.monthlyKwh.toFixed(2)}</td>
            <td>${naira.format(item.monthlyCost)}</td>
        `;

        tableBody.appendChild(row);
    });
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

function renderCharts(data) {
    if (typeof Chart === "undefined") {
        return;
    }

    const labels = data.map(item => item.name);

    if (usageChart) {
        usageChart.destroy();
    }

    usageChart = new Chart(document.getElementById("usageChart"), {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Daily energy usage (kWh)",
                data: data.map(item => item.dailyKwh),
                backgroundColor: "#3b82f6",
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: "kWh per day"
                    }
                }
            }
        }
    });

    if (costChart) {
        costChart.destroy();
    }

    costChart = new Chart(document.getElementById("costChart"), {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                label: "Monthly cost",
                data: data.map(item => item.monthlyCost),
                backgroundColor: [
                    "#2563eb",
                    "#14b8a6",
                    "#f59e0b",
                    "#8b5cf6",
                    "#ef4444",
                    "#64748b",
                    "#ec4899",
                    "#84cc16"
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom"
                },
                tooltip: {
                    callbacks: {
                        label: (context) =>
                            `${context.label}: ${naira.format(context.raw)}`
                    }
                }
            }
        }
    });
}

function renderReport(data) {
    const totalDaily = data.reduce((sum, item) => sum + item.dailyKwh, 0);
    const totalMonthly = data.reduce((sum, item) => sum + item.monthlyKwh, 0);
    const totalCost = data.reduce((sum, item) => sum + item.monthlyCost, 0);

    const monthLabel = monthInput.value
        ? new Date(`${monthInput.value}-02T12:00:00`).toLocaleDateString(
            "en-NG",
            { month: "long", year: "numeric" }
        )
        : "Selected month";

    document.getElementById("reportPeriod").textContent =
        `Report period: ${monthLabel} (${getMonthDays()} days)`;

    document.getElementById("reportContent").innerHTML = `
        <p><strong>Daily energy:</strong> ${totalDaily.toFixed(2)} kWh</p>
        <p><strong>Monthly energy:</strong> ${totalMonthly.toFixed(2)} kWh</p>
        <p><strong>Tariff:</strong> ${naira.format(getTariff())} per kWh</p>
        <p><strong>Estimated monthly cost:</strong> ${naira.format(totalCost)}</p>
        <p><strong>Appliances tracked:</strong> ${data.length}</p>
        <p class="muted">This report assumes the listed appliances run for the
        same number of hours every day. It is an estimate, not an actual
        electricity meter reading or utility bill.</p>
    `;
}

function updateDashboard() {
    const data = calculateAppliances();

    const dailyKwh = data.reduce((sum, item) => sum + item.dailyKwh, 0);
    const monthlyKwh = data.reduce((sum, item) => sum + item.monthlyKwh, 0);
    const dailyCost = data.reduce((sum, item) => sum + item.dailyCost, 0);
    const monthlyCost = data.reduce((sum, item) => sum + item.monthlyCost, 0);

    document.getElementById("dailyUsage").textContent =
        `${dailyKwh.toFixed(2)} kWh`;

    document.getElementById("monthlyUsage").textContent =
        `${monthlyKwh.toFixed(2)} kWh`;

    document.getElementById("dailyCost").textContent =
        naira.format(dailyCost);

    document.getElementById("monthlyCost").textContent =
        naira.format(monthlyCost);

    renderTable(data);
    renderCharts(data);
    renderReport(data);
}

tableBody.addEventListener("change", (event) => {
    const input = event.target;

    if (!input.matches("input[data-index][data-field]")) {
        return;
    }

    const index = Number(input.dataset.index);
    const field = input.dataset.field;

    if (!appliances[index]) {
        return;
    }

    if (field === "name") {
        appliances[index].name = input.value.trim() || "Unnamed appliance";
    } else {
        let value = Number(input.value);

        if (!Number.isFinite(value) || value < 0) {
            value = 0;
        }

        if (field === "hours") {
            value = Math.min(24, value);
        }

        appliances[index][field] = value;
    }

    updateDashboard();
});

document.getElementById("addAppliance").addEventListener("click", () => {
    appliances.push({
        name: "New Appliance",
        watts: 100,
        hours: 1
    });

    updateDashboard();
});

monthInput.addEventListener("change", updateDashboard);
tariffInput.addEventListener("input", updateDashboard);

const now = new Date();
monthInput.value =
    `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

updateDashboard();
