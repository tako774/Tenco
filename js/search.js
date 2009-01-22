// インクリメンタルサーチ
// 指定された各要素の配下のテキストを検索します 
function simple_inc_search(target_element, display_style, str_element, delay) {
	var target_element = target_element;
	var display_style = display_style;
	var str_element = str_element;
	var delay = delay;

	var before_str = "";
	
	setInterval(
		function() {
			var str = $(str_element).val();
			if (str != before_str) {
				// IE6 は show hide しか動かない 
				if (jQuery.browser.msie) {
					$(target_element).each(function() {
						if (str == "" || $(this).text().indexOf(str) != -1) {
							$(this).show();
						}
						else {
							$(this).hide();
						}
					});
				}
				// IE 以外は css の display を操作するほうが体感高速 
				else {
					$(target_element).each(function() {
						if (str == "" || $(this).text().indexOf(str) != -1) {
							$(this).css("display", display_style);
						}
						else {
							$(this).css("display", "none");
						}
					});
				}
			}
			before_str = str;
		},
		delay
	);
	
}	
