(function (window) {
    function createTotalMessagesChart() {
        var chartContainer = document.getElementById('totalMessageChartContainer');
        if (!chartContainer) return;

        var chartTitle = document.getElementById('chartTitle').textContent;

        // Access data attributes from the HTML
        var messagesSent = parseInt(chartContainer.getAttribute('data-messages-sent'));
        var messagesRemaining = parseInt(chartContainer.getAttribute('data-messages-remaining'));
        var totalMessages = messagesSent + messagesRemaining;

        // Update the message below the chart
        document.getElementById('message').innerText = `${messagesSent.toLocaleString()} sent / ${messagesRemaining.toLocaleString()} remaining`;

        // Calculate minimum width for "Messages Sent" as 1% of the total chart width
        var minSentPercentage = (messagesSent === 0) ? 0 : 0.02;
        var minSentValue = totalMessages * minSentPercentage;
        var displaySent = Math.max(messagesSent, minSentValue);
        var displayRemaining = totalMessages - displaySent;

        var svg = d3.select("#totalMessageChart");
        var width = chartContainer.clientWidth;
        var height = 48;

        // Ensure the width is set correctly
        if (width === 0) {
            console.error('Chart container width is 0, cannot set SVG width.');
            return;
        }

        svg.attr("width", width).attr("height", height);

        var x = d3.scaleLinear()
            .domain([0, totalMessages])
            .range([0, width]);

        // Create tooltip dynamically
        var tooltip = d3.select("body").append("div")
            .attr("id", "tooltip");

        // Create the initial bars
        var sentBar = svg.append("rect")
            .attr("x", 0)
            .attr("y", 0)
            .attr("height", height)
            .attr("fill", '#0076d6')
            .attr("width", 0) // Start with width 0 for animation
            .on('mouseover', function(event) {
                tooltip.style('display', 'block')
                    .html(`Messages Sent: ${messagesSent.toLocaleString()}`);
            })
            .on('mousemove', function(event) {
                tooltip.style('left', `${event.pageX + 10}px`)
                    .style('top', `${event.pageY - 20}px`);
            })
            .on('mouseout', function() {
                tooltip.style('display', 'none');
            });

        var remainingBar = svg.append("rect")
            .attr("x", 0) // Initially set to 0, will be updated during animation
            .attr("y", 0)
            .attr("height", height)
            .attr("fill", '#C7CACE')
            .attr("width", 0) // Start with width 0 for animation
            .on('mouseover', function(event) {
                tooltip.style('display', 'block')
                    .html(`Remaining: ${messagesRemaining.toLocaleString()}`);
            })
            .on('mousemove', function(event) {
                tooltip.style('left', `${event.pageX + 10}px`)
                    .style('top', `${event.pageY - 20}px`);
            })
            .on('mouseout', function() {
                tooltip.style('display', 'none');
            });

        // Animate the bars together as a single cohesive line
        svg.transition()
            .duration(1000)  // Total animation duration
            .attr("width", width)
            .tween("resize", function() {
                var interpolator = d3.interpolate(0, width);
                return function(t) {
                    var newWidth = interpolator(t);
                    var sentWidth = x(displaySent) / width * newWidth;
                    var remainingWidth = x(displayRemaining) / width * newWidth;
                    sentBar.attr("width", sentWidth);
                    remainingBar.attr("x", sentWidth).attr("width", remainingWidth);
                };
            });

        // Create and populate the accessible table
        var tableContainer = document.getElementById('totalMessageTable');
        var table = document.createElement('table');
        table.className = 'usa-sr-only usa-table';

        var caption = document.createElement('caption');
        caption.textContent = chartTitle;
        table.appendChild(caption);

        var thead = document.createElement('thead'); // Ensure thead is created
        var theadRow = document.createElement('tr');
        var thMessagesSent = document.createElement('th');
        thMessagesSent.textContent = 'Messages Sent'; // First column header
        var thRemaining = document.createElement('th');
        thRemaining.textContent = 'Remaining'; // Second column header
        theadRow.appendChild(thMessagesSent);
        theadRow.appendChild(thRemaining);
        thead.appendChild(theadRow); // Append theadRow to the thead
        table.appendChild(thead);

        var tbody = document.createElement('tbody');
        var tbodyRow = document.createElement('tr');

        var tdMessagesSent = document.createElement('td');
        tdMessagesSent.textContent = messagesSent.toLocaleString(); // Value for Messages Sent
        var tdRemaining = document.createElement('td');
        tdRemaining.textContent = messagesRemaining.toLocaleString(); // Value for Remaining

        tbodyRow.appendChild(tdMessagesSent);
        tbodyRow.appendChild(tdRemaining);
        tbody.appendChild(tbodyRow);

        table.appendChild(tbody);
        tableContainer.appendChild(table);

        table.appendChild(tbody);
        tableContainer.appendChild(table);

        // Ensure the chart resizes correctly on window resize
        window.addEventListener('resize', function () {
            width = chartContainer.clientWidth;
            x.range([0, width]);
            svg.attr("width", width);
            sentBar.attr("width", x(displaySent));
            remainingBar.attr("x", x(displaySent)).attr("width", x(displayRemaining));
        });
    }

    // Initialize total messages chart if the container exists
    document.addEventListener('DOMContentLoaded', function() {
        createTotalMessagesChart();
    });

    // Export function for testing
    window.createTotalMessagesChart = createTotalMessagesChart;

})(window);
