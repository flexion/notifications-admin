(function (window) {

    if (document.getElementById('activityChartContainer')) {
        let currentType = 'service';
        const tableContainer = document.getElementById('activityContainer');
        const currentUserName = tableContainer.getAttribute('data-currentUserName');
        const currentServiceId = tableContainer.getAttribute('data-currentServiceId');
        const COLORS = {
            delivered: '#0076d6',
            failed: '#fa9441',
            pending: '#C7CACE',
            text: '#666'
        };

        const FONT_SIZE = 16;
        const FONT_WEIGHT = 'bold';
        const MAX_Y = 120;

        const createChart = function(containerId, labels, deliveredData, failedData, pendingData) {
            const container = d3.select(containerId);
            container.selectAll('*').remove(); // Clear any existing content

            const margin = { top: 60, right: 20, bottom: 40, left: 20 }; // Adjusted top margin for legend
            const width = container.node().getBoundingClientRect().width - margin.left - margin.right;
            const height = 400 - margin.top - margin.bottom;

            const svg = container.append('svg')
                .attr('width', width + margin.left + margin.right)
                .attr('height', height + margin.top + margin.bottom)
                .append('g')
                .attr('transform', `translate(${margin.left},${margin.top})`);

            let tooltip = d3.select('#tooltip');

            if (tooltip.empty()) {
                tooltip = d3.select('body').append('div')
                    .attr('id', 'tooltip')
                    .style('display', 'none');
            }

            // Calculate total messages
            const totalMessages = d3.sum(deliveredData) + d3.sum(failedData) + d3.sum(pendingData);

            // Create legend only if there are messages
            const legendContainer = d3.select('.chart-legend');
            legendContainer.selectAll('*').remove(); // Clear any existing legend

            if (totalMessages > 0) {
                // Show legend if there are messages
                const legendData = [
                    { label: 'Delivered', color: COLORS.delivered },
                    { label: 'Failed', color: COLORS.failed },
                    { label: 'Pending', color: COLORS.pending }
                ];

                const legendItem = legendContainer.selectAll('.legend-item')
                    .data(legendData)
                    .enter()
                    .append('div')
                    .attr('class', 'legend-item');

                legendItem.append('div')
                    .attr('class', 'legend-rect')
                    .style('background-color', d => d.color)
                    .style('display', 'inline-block')
                    .style('margin-right', '5px');

                legendItem.append('span')
                    .attr('class', 'legend-label')
                    .text(d => d.label);

                // Ensure the legend is shown
                legendContainer.style('display', 'flex');
            } else {
                // Hide the legend if there are no messages
                legendContainer.style('display', 'none');
            }

            const x = d3.scaleBand()
                .domain(labels)
                .range([0, width])
                .padding(0.1);
                            // Adjust the y-axis domain to add some space above the tallest bar
            const maxY = d3.max(deliveredData.map((d, i) => d + (failedData[i] || 0) + (pendingData[i] || 0)));

            const y = d3.scaleSymlog()
                .domain([0, maxY + 2]) // Add 2 units of space at the top
                .nice()
                .range([height, 0]);

            svg.append('g')
                .attr('class', 'x axis')
                .attr('transform', `translate(0,${height})`)
                .call(d3.axisBottom(x));

            // Generate the y-axis with whole numbers
            const yAxis = d3.axisLeft(y)
                .ticks(Math.min(maxY + 2, 3))
                .tickFormat(d3.format('d')); // Ensure whole numbers on the y-axis

            svg.append('g')
                .attr('class', 'y axis')
                .call(yAxis);

            // Data for stacking
            const stackData = labels.map((label, i) => ({
                label: label,
                delivered: deliveredData[i],
                failed: failedData[i] || 0,
                pending: pendingData[i] || 0
            }));

            // Stack the data
            const stack = d3.stack()
                .keys(['delivered', 'failed', 'pending'])
                .order(d3.stackOrderNone)
                .offset(d3.stackOffsetNone);

            const series = stack(stackData);

            // Color scale
            const color = d3.scaleOrdinal()
                .domain(['delivered', 'failed', 'pending'])
                .range([COLORS.delivered, COLORS.failed, COLORS.pending]);

        // Create bars with animation
        const barGroups = svg.selectAll('.bar-group')
            .data(series)
            .enter()
            .append('g')
            .attr('class', 'bar-group')
            .attr('fill', d => color(d.key));
        const minBarHeight = 5;
        barGroups.selectAll('rect')
            .data(d => d)
            .enter()
            .append('rect')
            .filter(d => d[1] - d[0] > 0)
            .attr('x', d => x(d.data.label))
            .attr('y', height)
            .attr('height', 0)
            .attr('width', x.bandwidth())
            .on('mouseover', function(event, d) {
                const key = d3.select(this.parentNode).datum().key;
                const capitalizedKey = key.charAt(0).toUpperCase() + key.slice(1);
                tooltip.style('display', 'block')
                    .html(`${d.data.label}<br>${capitalizedKey}: ${d.data[key]}`);
            })
            .on('mousemove', function(event) {
                tooltip.style('left', `${event.pageX + 10}px`)
                    .style('top', `${event.pageY - 20}px`);
            })
            .on('mouseout', function() {
                tooltip.style('display', 'none');
            })
            .transition()
            .duration(1000)
            .attr('y', d => y(d[1]))
            .attr('height', d => {
                const calculatedHeight = y(d[0]) - y(d[1]);
                return calculatedHeight < minBarHeight ? minBarHeight : calculatedHeight;
            });    };

    // Function to create an accessible table
    const createTable = function(tableId, chartType, labels, deliveredData, failedData, pendingData) {
        const table = document.getElementById(tableId);
        table.innerHTML = ""; // Clear previous data

        const captionText = document.querySelector(`#${chartType} .chart-subtitle`).textContent;
        const caption = document.createElement('caption');
        caption.textContent = captionText;
        const thead = document.createElement('thead');
        const tbody = document.createElement('tbody');

        // Create table header
        const headerRow = document.createElement('tr');
        const headers = ['Day', 'Delivered', 'Failed', 'Pending'];
        headers.forEach(headerText => {
            const th = document.createElement('th');
            th.textContent = headerText;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        // Create table body
        labels.forEach((label, index) => {
            const row = document.createElement('tr');
            const cellDay = document.createElement('td');
            cellDay.textContent = label;
            row.appendChild(cellDay);

            const cellDelivered = document.createElement('td');
            cellDelivered.textContent = deliveredData[index];
            row.appendChild(cellDelivered);

            const cellFailed = document.createElement('td');
            cellFailed.textContent = failedData[index];
            row.appendChild(cellFailed);

            const cellPending = document.createElement('td');
            cellPending.textContent = pendingData[index];
            row.appendChild(cellPending);

            tbody.appendChild(row);
        });

        table.appendChild(caption);
        table.appendChild(thead);
        table.append(tbody);
    };

    const fetchData = function(type) {

        var ctx = document.getElementById('weeklyChart');
        if (!ctx) {
            return;
        }

        var userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        var url = type === 'service'
            ? `/services/${currentServiceId}/daily-stats.json?timezone=${encodeURIComponent(userTimezone)}`
            : `/services/${currentServiceId}/daily-stats-by-user.json?timezone=${encodeURIComponent(userTimezone)}`;


        return fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                labels = [];
                deliveredData = [];
                failedData = [];
                pendingData = [];
                let totalMessages = 0;

                for (var dateString in data) {
                    if (data.hasOwnProperty(dateString)) {
                        const dateParts = dateString.split('-');
                        const formattedDate = `${dateParts[1]}/${dateParts[2]}/${dateParts[0].slice(2)}`;

                        labels.push(formattedDate);
                        deliveredData.push(data[dateString].sms.delivered);
                        failedData.push(data[dateString].sms.failure);
                        pendingData.push(data[dateString].sms.pending || 0);
                        totalMessages += data[dateString].sms.delivered + data[dateString].sms.failure + data[dateString].sms.pending;
                    }
                }

                // Check if there are no messages sent
                const subTitle = document.querySelector(`#activityChartContainer .chart-subtitle`);
                if (totalMessages === 0) {
                    // Remove existing chart and render the alert message
                    d3.select('#weeklyChart').selectAll('*').remove();
                    d3.select('#weeklyChart')
                        .append('div')
                        .html(`
                            <div class="usa-alert usa-alert--info usa-alert--slim">
                                <div class="usa-alert__body">
                                    <p class="usa-alert__text">
                                        No messages sent in the last 7 days
                                    </p>
                                </div>
                            </div>
                        `);
                    // Hide the subtitle
                    if (subTitle) {
                        subTitle.style.display = 'none';
                    }
                } else {
                    // If there are messages, create the chart and table
                    createChart('#weeklyChart', labels, deliveredData, failedData, pendingData);
                    createTable('weeklyTable', 'activityChart', labels, deliveredData, failedData, pendingData);
                    }

                    return data;
                })
                .catch(error => console.error('Error fetching daily stats:', error));
        };
        setInterval(() => fetchData(currentType), 25000);
    const handleDropdownChange = function(event) {
        const selectedValue = event.target.value;
        currentType = selectedValue;
        const subTitle = document.querySelector(`#activityChartContainer .chart-subtitle`);
        const selectElement = document.getElementById('options');
        const selectedText = selectElement.options[selectElement.selectedIndex].text;

        subTitle.textContent = `${selectedText} - last 7 days`;
        fetchData(selectedValue);

        const liveRegion = document.getElementById('aria-live-account');
        liveRegion.textContent = `Data updated for ${selectedText} - last 7 days`;

        const tableHeading = document.querySelector('#tableActivity h2');
        const senderColumns = document.querySelectorAll('.sender-column');
        const allRows = document.querySelectorAll('#activity-table tbody tr');
        const caption = document.querySelector('#activity-table caption');

        if (selectedValue === 'individual') {

            tableHeading.textContent = 'My activity';
            caption.textContent = `Table showing the sent jobs for ${currentUserName}`;

            senderColumns.forEach(col => {
            col.style.display = 'none';
            });

            allRows.forEach(row => row.style.display = 'none');

            const userRows = Array.from(allRows).filter(row => {
                const senderCell = row.querySelector('.sender-column');
                const rowSender = senderCell ? senderCell.textContent.trim() : '';
                return rowSender === currentUserName;
            });

            if (userRows.length > 0) {
                userRows.slice(0, 5).forEach(row => {
                    row.style.display = '';
                });
            } else {
                const emptyMessageRow = Array.from(allRows).find(row => {
                    return row.querySelector('.table-empty-message');
                });
                if (emptyMessageRow) {
                    emptyMessageRow.style.display = '';
                }
            }
        } else {

            tableHeading.textContent = 'Service activity';
            caption.textContent = `Table showing the sent jobs for service`;

            senderColumns.forEach(col => {
            col.style.display = '';
            });

            allRows.forEach((row, index) => {
                row.style.display = (index < 5) ? '' : 'none';
            });
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        // Initialize activityChart chart and table with service data by default
        fetchData(currentType);

        const allRows = Array.from(document.querySelectorAll('#activity-table tbody tr'));
        allRows.forEach((row, index) => {
            row.style.display = (index < 5) ? '' : 'none';
        });

        const dropdown = document.getElementById('options');
        dropdown.addEventListener('change', handleDropdownChange);
    });

        // Resize chart on window resize
        window.addEventListener('resize', function() {
            if (labels.length > 0 && deliveredData.length > 0 && failedData.length > 0 && pendingData.length > 0) {
                createChart('#weeklyChart', labels, deliveredData, failedData, pendingData);
                createTable('weeklyTable', 'activityChart', labels, deliveredData, failedData, pendingData);
            }
        });

        // Export functions for testing
        window.createChart = createChart;
        window.createTable = createTable;
        window.handleDropdownChange = handleDropdownChange;
        window.fetchData = fetchData;
    }

})(window);
