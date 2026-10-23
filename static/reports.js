(function () {
  "use strict";

  // --- Initial Data Setup ---
  let appliances = [];
  try {
    const raw = document.getElementById("serverAppliances");
    if (raw && raw.textContent) {
      appliances = JSON.parse(raw.textContent);
    }
  } catch (e) {
    appliances = [];
  }

  // Fallback defaults if no user appliances exist yet
  if (!appliances || appliances.length === 0) {
    appliances = [
      { name: "Refrigerator", wattage: 200, hours_per_day: 24, quantity: 1 },
      { name: "Air Conditioner", wattage: 1500, hours_per_day: 6, quantity: 1 },
      { name: "Standing Fan", wattage: 65, hours_per_day: 10, quantity: 2 },
      { name: "Smart TV", wattage: 100, hours_per_day: 5, quantity: 1 },
      { name: "LED Lighting", wattage: 60, hours_per_day: 7, quantity: 1 }
    ];
  }

  let tariffInput = document.getElementById("tariff");
  let reportMonthInput = document.getElementById("reportMonth");
  let dailyUsageEl = document.getElementById("dailyUsage");
  let monthlyUsageEl = document.getElementById("monthlyUsage");
  let dailyCostEl = document.getElementById("dailyCost");
  let monthlyCostEl = document.getElementById("monthlyCost");
  let tableBody = document.getElementById("applianceTable");
  let reportPeriodEl = document.getElementById("reportPeriod");
  let reportContentEl = document.getElementById("reportContent");
  let addApplianceBtn = document.getElementById("addAppliance");

  // Set default month to current year-month
  if (reportMonthInput && !reportMonthInput.value) {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    reportMonthInput.value = `${yyyy}-${mm}`;
  }

  function getTariff() {
    return parseFloat(tariffInput ? tariffInput.value : 68.0) || 68.0;
  }

  function formatCurrency(val) {
    return "₦" + Number(val).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function formatKwh(val) {
    return Number(val).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " kWh";
  }

  function getThemeColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      isDark: isDark,
      textColor: isDark ? "#F3F6F8" : "#173239",
      mutedColor: isDark ? "#A5B5B9" : "#5F7078",
      gridColor: isDark ? "rgba(243, 246, 248, 0.08)" : "rgba(23, 50, 57, 0.07)",
      barBg: isDark ? "#32B5A2" : "#167D70",
      barHover: isDark ? "#48cbba" : "#115B53",
      tooltipBg: isDark ? "#192C32" : "#173239",
      doughnutColors: [
        "#167D70",
        "#D7F36B",
        "#32B5A2",
        "#115B53",
        "#86EFAC",
        "#EAB308",
        "#06B6D4",
        "#F43F5E",
        "#A855F7"
      ]
    };
  }

  // --- Charts Instance Holders ---
  let usageChart = null;
  let costChart = null;

  function initCharts() {
    const usageCanvas = document.getElementById("usageChart");
    const costCanvas = document.getElementById("costChart");
    if (!usageCanvas || !costCanvas || typeof Chart === "undefined") return;

    const theme = getThemeColors();

    usageChart = new Chart(usageCanvas, {
      type: "bar",
      data: {
        labels: [],
        datasets: [{
          label: "Daily Consumption (kWh)",
          data: [],
          backgroundColor: theme.barBg,
          hoverBackgroundColor: theme.barHover,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.tooltipBg,
            titleColor: "#FFFFFF",
            bodyColor: "#FFFFFF",
            padding: 10,
            callbacks: {
              label: (ctx) => `${ctx.parsed.y.toFixed(2)} kWh / day`
            }
          }
        },
        scales: {
          x: {
            ticks: { color: theme.mutedColor },
            grid: { display: false }
          },
          y: {
            ticks: {
              color: theme.mutedColor,
              callback: (v) => v + " kWh"
            },
            grid: { color: theme.gridColor }
          }
        }
      }
    });

    costChart = new Chart(costCanvas, {
      type: "doughnut",
      data: {
        labels: [],
        datasets: [{
          data: [],
          backgroundColor: theme.doughnutColors,
          borderWidth: 2,
          borderColor: theme.isDark ? "#192C32" : "#FFFFFF"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: theme.textColor,
              boxWidth: 12,
              padding: 14
            }
          },
          tooltip: {
            backgroundColor: theme.tooltipBg,
            titleColor: "#FFFFFF",
            bodyColor: "#FFFFFF",
            callbacks: {
              label: (ctx) => ` ₦${ctx.parsed.toLocaleString()} (${ctx.label})`
            }
          }
        }
      }
    });
  }

  function updateChartTheme() {
    if (!usageChart || !costChart) return;
    const theme = getThemeColors();

    // Bar chart theme update
    usageChart.data.datasets[0].backgroundColor = theme.barBg;
    usageChart.data.datasets[0].hoverBackgroundColor = theme.barHover;
    usageChart.options.scales.x.ticks.color = theme.mutedColor;
    usageChart.options.scales.y.ticks.color = theme.mutedColor;
    usageChart.options.scales.y.grid.color = theme.gridColor;
    usageChart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
    usageChart.update();

    // Doughnut chart theme update
    costChart.data.datasets[0].borderColor = theme.isDark ? "#192C32" : "#FFFFFF";
    costChart.options.plugins.legend.labels.color = theme.textColor;
    costChart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
    costChart.update();
  }

  function render() {
    const tariff = getTariff();
    let totalDailyKwh = 0;
    let totalMonthlyKwh = 0;
    let totalMonthlyCost = 0;

    const enriched = appliances.map((item, index) => {
      const qty = parseInt(item.quantity, 10) || 1;
      const watts = parseFloat(item.wattage) || 0;
      const hours = parseFloat(item.hours_per_day) || 0;

      const dailyKwh = (watts * qty * hours) / 1000.0;
      const monthlyKwh = dailyKwh * 30;
      const monthlyCost = monthlyKwh * tariff;

      totalDailyKwh += dailyKwh;
      totalMonthlyKwh += monthlyKwh;
      totalMonthlyCost += monthlyCost;

      return {
        ...item,
        index: index,
        dailyKwh: dailyKwh,
        monthlyKwh: monthlyKwh,
        monthlyCost: monthlyCost
      };
    });

    const dailyCost = totalDailyKwh * tariff;

    // Update Summary cards
    if (dailyUsageEl) dailyUsageEl.textContent = formatKwh(totalDailyKwh);
    if (monthlyUsageEl) monthlyUsageEl.textContent = formatKwh(totalMonthlyKwh);
    if (dailyCostEl) dailyCostEl.textContent = formatCurrency(dailyCost);
    if (monthlyCostEl) monthlyCostEl.textContent = formatCurrency(totalMonthlyCost);

    // Update Table
    if (tableBody) {
      tableBody.innerHTML = "";
      enriched.forEach((app, i) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><input type="text" class="appliance-name" value="${app.name || "Appliance"}" data-index="${i}" data-field="name"></td>
          <td><input type="number" min="0" value="${app.wattage || 0}" data-index="${i}" data-field="wattage"></td>
          <td><input type="number" min="0" max="24" step="0.5" value="${app.hours_per_day || 0}" data-index="${i}" data-field="hours_per_day"></td>
          <td>${app.dailyKwh.toFixed(2)} kWh</td>
          <td>${app.monthlyKwh.toFixed(2)} kWh</td>
          <td>${formatCurrency(app.monthlyCost)}</td>
          <td><button type="button" class="btn-remove" title="Remove" data-remove="${i}">×</button></td>
        `;
        tableBody.appendChild(row);
      });
    }

    // Update Period label
    if (reportPeriodEl && reportMonthInput) {
      const val = reportMonthInput.value;
      if (val) {
        const [yr, mo] = val.split("-");
        const dt = new Date(yr, parseInt(mo, 10) - 1, 1);
        const name = dt.toLocaleString("en-US", { month: "long", year: "numeric" });
        reportPeriodEl.textContent = `Billing period: ${name}`;
      } else {
        reportPeriodEl.textContent = "Estimated 30-Day Period";
      }
    }

    // Update Report Text Summary
    if (reportContentEl) {
      const sorted = [...enriched].sort((a, b) => b.monthlyCost - a.monthlyCost);
      const topConsumer = sorted[0];
      const savings20 = totalMonthlyCost * 0.20;

      reportContentEl.innerHTML = `
        <p><strong>Total Estimated Monthly Bill:</strong> ${formatCurrency(totalMonthlyCost)} (${formatKwh(totalMonthlyKwh)})</p>
        <p><strong>Daily Electricity Expense:</strong> ${formatCurrency(dailyCost)} per day</p>
        ${topConsumer ? `<p><strong>Highest Consumer:</strong> ${topConsumer.name} contributes ${((topConsumer.monthlyCost / (totalMonthlyCost || 1)) * 100).toFixed(1)}% of your overall bill (${formatCurrency(topConsumer.monthlyCost)}/mo).</p>` : ""}
        <p><strong>Potential 20% Energy Savings:</strong> Lowering daily runtimes or turning off idle appliances could save <strong>${formatCurrency(savings20)}</strong> every month.</p>
      `;
    }

    // Update Charts
    if (usageChart) {
      usageChart.data.labels = enriched.map(a => a.name || "Appliance");
      usageChart.data.datasets[0].data = enriched.map(a => parseFloat(a.dailyKwh.toFixed(2)));
      usageChart.update();
    }

    if (costChart) {
      costChart.data.labels = enriched.map(a => a.name || "Appliance");
      costChart.data.datasets[0].data = enriched.map(a => Math.round(a.monthlyCost));
      costChart.update();
    }
  }

  // --- Event Listeners ---
  if (tariffInput) {
    tariffInput.addEventListener("input", render);
  }

  if (reportMonthInput) {
    reportMonthInput.addEventListener("change", render);
  }

  if (tableBody) {
    tableBody.addEventListener("input", function (e) {
      const idx = e.target.dataset.index;
      const field = e.target.dataset.field;
      if (idx !== undefined && field) {
        let val = e.target.value;
        if (field === "wattage" || field === "hours_per_day") {
          val = parseFloat(val) || 0;
        }
        appliances[idx][field] = val;
        render();
      }
    });

    tableBody.addEventListener("click", function (e) {
      const removeBtn = e.target.closest("[data-remove]");
      if (removeBtn) {
        const idx = parseInt(removeBtn.dataset.remove, 10);
        appliances.splice(idx, 1);
        render();
      }
    });
  }

  if (addApplianceBtn) {
    addApplianceBtn.addEventListener("click", function () {
      appliances.push({
        name: "New Appliance",
        wattage: 100,
        hours_per_day: 4,
        quantity: 1
      });
      render();
    });
  }

  // Observe theme changes on documentElement
  const themeObserver = new MutationObserver(function (mutations) {
    for (const m of mutations) {
      if (m.attributeName === "data-theme") {
        updateChartTheme();
      }
    }
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // Initialize charts and render on page load
  window.addEventListener("DOMContentLoaded", function () {
    initCharts();
    render();
  });

  // Fallback if DOM already loaded
  if (document.readyState === "complete" || document.readyState === "interactive") {
    initCharts();
    render();
  }
})();
