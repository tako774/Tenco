function timechart(times) {
	var canvas = document.getElementById("timechart");
	var ctx = canvas.getContext("2d");
	var r_x = 105;
	var r_y = 105;
	var r_r = 100;
	var days = 180;
	var now = new Date();
	var hour = now.getHours();
	var dates = [];
	
	var limits = 100;
	
	$("td.time").each(function(){
		var d = new Date("20" + $(this).text());
		if ((now.getTime() - d.getTime()) / (86400 * 1000) < days) {	
			dates.push(d);
		}
		else {
			return false;
		}
	});
	
	ctx.fillStyle = "#F4F4F4";
	ctx.beginPath();
	ctx.arc(
		r_x,
		r_y,
		r_r * 46 / 116,
		0,
		2 * Math.PI,
		false
	);
	ctx.lineTo(
		r_x + r_r,
		r_y
	);
	ctx.arc(
		r_x,
		r_y,
		r_r,
		0,
		2 * Math.PI,
		true
	);
	ctx.closePath();
	ctx.fill();

	ctx.fillStyle = "#FFE0B0";
	ctx.beginPath();
	ctx.arc(
		r_x,
		r_y,
		r_r * 46 / 116,
		(hour / 12 - 0.5) * Math.PI,
		((hour + 1) / 12 - 0.5) * Math.PI,
		false
	);
	ctx.lineTo(
		r_x + r_r * Math.cos(((hour + 1) / 12 - 0.5) * Math.PI),
		r_y + r_r * Math.sin(((hour + 1) / 12 - 0.5) * Math.PI)
	);
	ctx.arc(
		r_x,
		r_y,
		r_r,
		((hour + 1) / 12 - 0.5) * Math.PI,
		(hour / 12 - 0.5) * Math.PI,
		true
	);
	ctx.closePath();
	ctx.fill();

	
	ctx.lineWidth = 1;
	ctx.strokeStyle = "#666666";
	ctx.beginPath();
	ctx.arc(r_x, r_y, r_r * 120 / 116, 0 * Math.PI, 2 * Math.PI, false);
	ctx.stroke();
	
	ctx.strokeStyle = "#D8D8D8";
	ctx.beginPath();
	ctx.arc(r_x, r_y, r_r * 116 / 116, 0 * Math.PI, 2 * Math.PI, false);
	ctx.stroke();
	ctx.beginPath();
	ctx.arc(r_x, r_y, r_r * 46 / 116, 0 * Math.PI, 2 * Math.PI, false);
	ctx.stroke();
	ctx.beginPath();
	ctx.arc(r_x, r_y, r_r * 17 / 116, 0 * Math.PI, 2 * Math.PI, false);
	ctx.stroke();
	
	ctx.strokeStyle = "#666666";
	ctx.beginPath();
	ctx.arc(r_x, r_y, r_r * 15 / 116, 0 * Math.PI, 2 * Math.PI, false);
	ctx.stroke();
	
	ctx.lineWidth = 1;
	ctx.strokeStyle = "#CCCCCC";
	for (var i = 0; i < 24; i++) {
		ctx.beginPath();
		ctx.moveTo(r_x + (r_r * 46 / 116)  * Math.cos((i / 24) * 2 * Math.PI), r_y + (r_r * 46 / 116) * Math.sin((i / 24) * 2 * Math.PI));
		ctx.lineTo(r_x + r_r * Math.cos((i / 24) * 2 * Math.PI), r_y + r_r * Math.sin((i / 24) * 2 * Math.PI));
		ctx.stroke();	
	}
	
	ctx.lineWidth = (r_r * 70 / 116) / days;
	ctx.strokeStyle = "#FFA500";
	
	for (var i in dates) {
		var t_date = dates[i];
		var t_hour = t_date.getHours();
		var t_minute = t_date.getMinutes();
		var round = (now.getTime() - t_date.getTime()) / (86400 * 1000);
		var radius = (r_r - (round + 0.5) * ctx.lineWidth);
		
		if (radius > r_r / 3) {
			ctx.beginPath();
			ctx.arc(
				r_x,
				r_y,
				radius,
				((t_hour + (t_minute - 10) / 60) / 12 - 0.5) * Math.PI,
				((t_hour + t_minute / 60) / 12 - 0.5) * Math.PI,
				false
			);
			ctx.stroke();
		}
	}
}
	