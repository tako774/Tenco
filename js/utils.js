function getTimeStr(date) {
	var hour = date.getHours(); // 時
	var min = date.getMinutes(); // 分
	var sec = date.getSeconds(); // 秒

	if (hour  < 10) { hour = "0" + hour; }
	if (min   < 10) { min = "0" + min; }
	if (sec   < 10) { sec = "0" + sec; }

	str = hour + '時' + min + '分' + sec + '秒'
	return str
}
