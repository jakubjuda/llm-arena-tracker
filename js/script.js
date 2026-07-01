        // Global tracker variables for managing dynamic toggling state
        let chartInstance = null;
        let allModelsVisible = true;

        // Organization base hues for distinct, readable grouping
        const orgHues = {
            'Anthropic': 260, // Purple
            'OpenAI': 150,    // Green
            'Google': 210,    // Blue
            'Z.ai': 175,      // Teal
            'MiniMax': 25,    // Orange
            'Xiaomi': 0,      // Red
            'Moonshot': 230,  // Indigo
            'Alibaba': 45     // Yellow
        };

        // Distributes lightness evenly across models in the same organization
        function getModelColor(org, modelName, orgModelArrays) {
            // Fallback dynamic hue if the org isn't hardcoded in our map
            const baseHue = orgHues[org] !== undefined ? orgHues[org] : (Math.abs(org.charCodeAt(0)) * 30 % 360);

            const modelsInOrg = orgModelArrays[org] || [];
            const index = modelsInOrg.indexOf(modelName);
            const total = modelsInOrg.length;

            const saturation = 75; // Balanced saturation

            // Spread lightness from 35% (darker variants) to 75% (lighter variants)
            let lightness = 50;
            if (total > 1) {
                const step = 40 / (total - 1);
                lightness = 35 + (index * step);
            }

            return `hsl(${baseHue}, ${saturation}%, ${lightness}%)`;
        }

        async function initChart() {
            const statusDiv = document.getElementById('statusMessage');
            const toggleBtn = document.getElementById('masterToggleBtn');

            try {
                const response = await fetch('./data/history.json');
                if (!response.ok) throw new Error(`HTTP Status Error: ${response.status}`);

                const rawData = await response.json();

                if (!Array.isArray(rawData) || rawData.length === 0) {
                    statusDiv.innerHTML = `<strong>No Data Available:</strong> The history dataset is empty.`;
                    return;
                }

                // Robust chronological sort using native Date objects
                rawData.sort((a, b) => new Date(a.date) - new Date(b.date));

                const labels = rawData.map(entry => entry.date);
                const totalDays = rawData.length;

                // Map models to organizations AND group them into arrays
                const modelsInfo = {};
                const orgGroups = {};

                rawData.forEach(day => {
                    if (!day.models) return;
                    day.models.forEach(model => {
                        const orgName = model.org || 'Unknown';
                        if (!modelsInfo[model.name]) {
                            modelsInfo[model.name] = orgName;
                        }
                        if (!orgGroups[orgName]) {
                            orgGroups[orgName] = new Set();
                        }
                        orgGroups[orgName].add(model.name);
                    });
                });

                // Convert sets to sorted arrays so the lightness distribution remains entirely deterministic
                const orgModelArrays = {};
                for (const org in orgGroups) {
                    orgModelArrays[org] = Array.from(orgGroups[org]).sort();
                }

                const modelNamesArray = Object.keys(modelsInfo);

                // Pre-allocate matrix structures
                const modelDataMap = {};
                modelNamesArray.forEach(name => {
                    modelDataMap[name] = new Array(totalDays).fill(null);
                });

                // Populate data matrix
                rawData.forEach((dayEntry, dayIndex) => {
                    if (!dayEntry.models) return;
                    dayEntry.models.forEach(model => {
                        modelDataMap[model.name][dayIndex] = model.score;
                    });
                });

                // Assemble datasets
                let datasets = modelNamesArray.map(modelName => {
                    const org = modelsInfo[modelName];
                    const uniqueColor = getModelColor(org, modelName, orgModelArrays);
                    const dataArray = modelDataMap[modelName];

                    // Read backward to acquire latest active score for ranking sort
                    let currentScore = 0;
                    for (let i = dataArray.length - 1; i >= 0; i--) {
                        if (dataArray[i] !== null) {
                            currentScore = dataArray[i];
                            break;
                        }
                    }

                    return {
                        label: modelName,
                        orgName: org,
                        data: dataArray,
                        borderColor: uniqueColor,
                        backgroundColor: uniqueColor,
                        borderWidth: 3,
                        tension: 0.15,
                        pointRadius: 0,
                        hoverRadius: 7,
                        pointHoverBorderWidth: 2,
                        pointHoverBackgroundColor: '#ffffff',
                        spanGaps: true,
                        latestRankScore: currentScore
                    };
                });

                // Sort datasets by current highest score to structure the graph stack cleanly
                datasets.sort((a, b) => b.latestRankScore - a.latestRankScore);

                statusDiv.style.display = 'none';
                const canvas = document.getElementById('eloChart');
                canvas.style.display = 'block';
                toggleBtn.style.display = 'block'; // Make button visible now that data exists

                // Initialize Chart instance globally accessible variable
                chartInstance = new Chart(canvas.getContext('2d'), {
                    type: 'line',
                    data: { labels: labels, datasets: datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        layout: {
                            padding: { left: 10, right: 20, top: 10, bottom: 10 }
                        },
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        plugins: {
                            legend: {
                                position: 'bottom',
                                align: 'center',
                                labels: {
                                    boxWidth: 12,
                                    padding: 15,
                                    font: { size: 12, weight: '500' }
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(17, 24, 39, 0.95)',
                                padding: 12,
                                titleFont: { size: 13, weight: 'bold' },
                                bodyFont: { size: 12 },
                                cornerRadius: 6,
                                itemSort: (a, b) => b.raw - a.raw,
                                callbacks: {
                                    filter: function (tooltipItem) {
                                        return tooltipItem.chart.isDatasetVisible(tooltipItem.datasetIndex);
                                    },
                                    footer: (tooltipItems) => {
                                        if (tooltipItems.length > 12) {
                                            return `\n... and ${tooltipItems.length - 12} more models`;
                                        }
                                        return null;
                                    },
                                    label: function (context) {
                                        const dataPoints = context.chart.tooltip.dataPoints || [];
                                        const indexInTooltip = dataPoints.findIndex(dp => dp.datasetIndex === context.datasetIndex);

                                        const activeElements = context.chart.getActiveElements();
                                        const isHovered = activeElements.length > 0 && activeElements[0].datasetIndex === context.datasetIndex;

                                        if (indexInTooltip >= 12 && !isHovered) {
                                            return null;
                                        }

                                        const org = context.dataset.orgName;
                                        return ` #${indexInTooltip + 1} ${context.dataset.label} (${org}): ${context.raw.toFixed(1)}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { display: false },
                                ticks: {
                                    padding: 10,
                                    callback: function (val, index) {
                                        return index % 7 === 0 ? this.getLabelForValue(val) : '';
                                    },
                                    autoSkip: false
                                },
                                title: { display: true, text: 'Timeline (Date)', font: { weight: 'bold' }, padding: 10 }
                            },
                            y: {
                                grid: { color: '#f3f4f6' },
                                ticks: { padding: 12 },
                                title: { display: true, text: 'Score', font: { weight: 'bold' }, padding: 10 }
                            }
                        }
                    }
                });

                // Attach Click Event Listener for the Master Toggle Trigger
                toggleBtn.addEventListener('click', () => {
                    allModelsVisible = !allModelsVisible;

                    // Modify visibility setting across entire dataset collection
                    chartInstance.data.datasets.forEach((_, index) => {
                        chartInstance.setDatasetVisibility(index, allModelsVisible);
                    });

                    // Redraw canvas context mapping updates instantly
                    chartInstance.update();

                    // Mutate button aesthetics and text tracking values
                    if (allModelsVisible) {
                        toggleBtn.textContent = 'Hide All Models';
                        toggleBtn.classList.remove('all-hidden');
                    } else {
                        toggleBtn.textContent = 'Show All Models';
                        toggleBtn.classList.add('all-hidden');
                    }
                });

            } catch (error) {
                statusDiv.style.color = '#dc2626';
                statusDiv.innerHTML = `<strong>Optimization Failed:</strong> ${error.message}`;
            }
        }

        initChart();
