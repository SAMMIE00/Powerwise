(function () {
  "use strict";

  const dataElement = document.getElementById("serverAppliances");
  if (!dataElement) return;

  const historyElement = document.getElementById("serverHistory");
  const appliances = JSON.parse(dataElement.textContent || "[]");
  const historyRecords = JSON.parse((historyElement && historyElement.textContent) || "[]");

  const usageCanvas = document.getElementById("usageChart");
  const costCanvas = document.getElementById("costChart");
  const reportMonthInput = document.getElementById("reportMonth");
  const reportPeriod = document.getElementById("reportPeriod");
  const tariffInput = document.getElementById("tariff");
  const tableBody = document.getElementById("applianceTable");
  const dailyUsage = document.getElementById("dailyUsage");
  const monthlyUsage = document.getElementById("monthlyUsage");
  const dailyCost = document.getElementById("dailyCost");
  const monthlyCost = document.getElementById("monthlyCost");
  const reportContent = document.getElementById("reportContent");

  const rate = Number(tariffInput && tariffInput.value) || 68.0;
  const formatKwh = (value) => `${Number(value).toFixed(2)} kWh`;
  const formatCurrency = (value) => `₦${Number(value).toLocaleString("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;

  let usageChart = null;
  let costChart = null;

  function getCurrentMonth() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  }

  function getReportDataForMonth(selectedMonth) {
    if (selectedMonth === getCurrentMonth() && appliances.length > 0) {
      const totalDailyKwh = appliances.reduce((sum, a) => sum + Number(a.daily_kwh || 0), 0);
      const totalMonthlyKwh = appliances.reduce((sum, a) => sum + Number(a.monthly_kwh || 0), 0);
      const totalMonthlyCost = appliances.reduce((sum, a) => sum + Number(a.monthly_cost || 0), 0);
      return {
        hasData: true,
        appliances: appliances,
        totalDailyKwh: totalDailyKwh,
        totalMonthlyKwh: totalMonthlyKwh,
        totalMonthlyCost: totalMonthlyCost,
        rate: rate
      };
    }

    const match = historyRecords.find((rec) => rec.recorded_month === selectedMonth);
    if (match) {
      const mKwh = Number(match.energy_consumption || 0);
      const mCost = Number(match.estimated_cost || 0);
      const histRate = Number(match.tariff_rate || rate);
      return {
        hasData: true,
        appliances: appliances,
        totalDailyKwh: mKwh / 30,
        totalMonthlyKwh: mKwh,
        totalMonthlyCost: mCost,
        rate: histRate
      };
    }

    return {
      hasData: false,
      appliances: [],
      totalDailyKwh: 0,
      totalMonthlyKwh: 0,
      totalMonthlyCost: 0,
      rate: rate
    };
  }

  function renderReport() {
    const selectedMonth = reportMonthInput ? reportMonthInput.value : getCurrentMonth();
    const data = getReportDataForMonth(selectedMonth);

    if (dailyUsage) dailyUsage.textContent = data.hasData ? formatKwh(data.totalDailyKwh) : "—";
    if (monthlyUsage) monthlyUsage.textContent = data.hasData ? formatKwh(data.totalMonthlyKwh) : "—";
    if (dailyCost) dailyCost.textContent = data.hasData ? formatCurrency(data.totalDailyKwh * data.rate) : "—";
    if (monthlyCost) monthlyCost.textContent = data.hasData ? formatCurrency(data.totalMonthlyCost) : "—";

    if (tableBody) {
      tableBody.replaceChildren();
      if (data.hasData) {
        data.appliances.forEach((appliance) => {
          const row = document.createElement("tr");
          [
            appliance.name || "Appliance",
            `${Number(appliance.wattage || 0).toLocaleString("en-NG")} W`,
            String(appliance.quantity || 1),
            `${Number(appliance.hours_per_day || 0).toFixed(1)} hrs`,
            formatKwh(appliance.daily_kwh || 0),
            formatKwh(appliance.monthly_kwh || 0),
            formatCurrency(appliance.monthly_cost || 0)
          ].forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
          });
          tableBody.appendChild(row);
        });
      } else {
        const emptyRow = document.createElement("tr");
        const emptyCell = document.createElement("td");
        emptyCell.colSpan = 7;
        emptyCell.style.textAlign = "center";
        emptyCell.style.padding = "2rem";
        emptyCell.style.color = "var(--muted)";
        emptyCell.textContent = "No appliance data or recorded usage for " + selectedMonth + ".";
        emptyRow.appendChild(emptyCell);
        tableBody.appendChild(emptyRow);
      }
    }

    if (reportContent) {
      reportContent.replaceChildren();
      if (data.hasData) {
        const highestConsumer = data.appliances.reduce((highest, appliance) =>
          !highest || Number(appliance.monthly_kwh) > Number(highest.monthly_kwh) ? appliance : highest, null);

        const reportLines = [
          `Total Estimated Monthly Bill: ${formatCurrency(data.totalMonthlyCost)} (${formatKwh(data.totalMonthlyKwh)})`,
          `Daily Electricity Expense: ${formatCurrency(data.totalDailyKwh * data.rate)} per day`
        ];

        if (highestConsumer) {
          const share = data.totalMonthlyKwh > 0
            ? (Number(highestConsumer.monthly_kwh) / data.totalMonthlyKwh * 100).toFixed(1)
            : "0.0";
          reportLines.push(
            `Highest Consumer: ${highestConsumer.name} contributes ${share}% of total usage (${formatCurrency(highestConsumer.monthly_cost)}/mo).`
          );
        }
        reportLines.push(`Potential 20% Energy Savings: ${formatCurrency(data.totalMonthlyCost * 0.2)} every month.`);

        reportLines.forEach((line) => {
          const paragraph = document.createElement("p");
          paragraph.textContent = line;
          reportContent.appendChild(paragraph);
        });
      } else {
        const emptyPara = document.createElement("p");
        emptyPara.className = "muted";
        emptyPara.textContent = "No billing data found for " + selectedMonth + ".";
        reportContent.appendChild(emptyPara);
      }
    }

    if (usageChart && costChart) {
      if (data.hasData && data.appliances.length > 0) {
        usageChart.data.labels = data.appliances.map((a) => a.name);
        usageChart.data.datasets[0].data = data.appliances.map((a) => a.daily_kwh);
        costChart.data.labels = data.appliances.map((a) => a.name);
        costChart.data.datasets[0].data = data.appliances.map((a) => a.monthly_cost);
      } else {
        usageChart.data.labels = [];
        usageChart.data.datasets[0].data = [];
        costChart.data.labels = [];
        costChart.data.datasets[0].data = [];
      }
      usageChart.update();
      costChart.update();
    }
  }

  function updateReportPeriod() {
    if (!reportMonthInput || !reportPeriod || !reportMonthInput.value) return;

    const [year, month] = reportMonthInput.value.split("-");
    const date = new Date(Number(year), Number(month) - 1, 1);
    const monthName = date.toLocaleString("en-US", { month: "long", year: "numeric" });
    const data = getReportDataForMonth(reportMonthInput.value);

    if (data.hasData) {
      reportPeriod.textContent = `Billing period: ${monthName} · Tariff rate: ${formatCurrency(data.rate)}/kWh`;
    } else {
      reportPeriod.textContent = `No recorded report found for ${monthName}.`;
    }
    renderReport();
  }

  if (reportMonthInput) {
    reportMonthInput.value = getCurrentMonth();
    reportMonthInput.addEventListener("change", updateReportPeriod);
    updateReportPeriod();
  } else {
    renderReport();
  }

  if (!usageCanvas || !costCanvas || typeof Chart === "undefined") return;

  function getThemeColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      isDark,
      textColor: isDark ? "#F3F6F8" : "#173239",
      mutedColor: isDark ? "#A5B5B9" : "#5F7078",
      gridColor: isDark ? "rgba(243, 246, 248, 0.08)" : "rgba(23, 50, 57, 0.07)",
      barBg: isDark ? "#32B5A2" : "#167D70",
      tooltipBg: isDark ? "#192C32" : "#173239",
      doughnutColors: [
        "#167D70", "#D7F36B", "#32B5A2", "#115B53", "#86EFAC",
        "#EAB308", "#06B6D4", "#F43F5E", "#A855F7"
      ]
    };
  }

  const theme = getThemeColors();
  usageChart = new Chart(usageCanvas, {
    type: "bar",
    data: {
      labels: [],
      datasets: [{
        label: "Daily Consumption (kWh)",
        data: [],
        backgroundColor: theme.barBg,
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
          callbacks: {
            label: (context) => `${Number(context.parsed.y).toFixed(2)} kWh / day`
          }
        }
      },
      scales: {
        x: { ticks: { color: theme.mutedColor }, grid: { display: false } },
        y: {
          ticks: { color: theme.mutedColor, callback: (value) => `${value} kWh` },
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
          labels: { color: theme.textColor, boxWidth: 12, padding: 14 }
        },
        tooltip: {
          backgroundColor: theme.tooltipBg,
          callbacks: {
            label: (context) => ` ₦${Number(context.parsed).toLocaleString()} (${context.label})`
          }
        }
      }
    }
  });

  renderReport();

  const themeObserver = new MutationObserver(() => {
    const currentTheme = getThemeColors();
    usageChart.data.datasets[0].backgroundColor = currentTheme.barBg;
    usageChart.options.scales.x.ticks.color = currentTheme.mutedColor;
    usageChart.options.scales.y.ticks.color = currentTheme.mutedColor;
    usageChart.options.scales.y.grid.color = currentTheme.gridColor;
    usageChart.options.plugins.tooltip.backgroundColor = currentTheme.tooltipBg;
    usageChart.update();

    costChart.data.datasets[0].borderColor = currentTheme.isDark ? "#192C32" : "#FFFFFF";
    costChart.options.plugins.legend.labels.color = currentTheme.textColor;
    costChart.options.plugins.tooltip.backgroundColor = currentTheme.tooltipBg;
    costChart.update();
  });

  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"]
  });
})();
