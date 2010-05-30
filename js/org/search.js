// 検索
// 指定された各要素の配下のテキストを検索します
var lock_search_process = 0;
var before_str = "";

function search(target_element, display_style, str_element) {
	if (lock_search_process == 0) {
		lock_search_process = 1;
	
		var target_element = target_element;
		var display_style = display_style;
		var str_element = str_element;
		
		// 検索文字列取得
		var str = $(str_element).val();
		
		if (str != before_str) {
			var default_search_tool_msg = $("#search_tool_msg").text();
			$("#search_tool_msg").text("検索中");
			
			before_str = str;
			
			if (str != "") {
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
			else {
				// IE6 は show hide しか動かない 
				if (jQuery.browser.msie) {
					$(target_element).show();
				}
				// IE 以外は css の display を操作するほうが体感高速 
				else {
					$(target_element).css("display", display_style);
				}
			}
			
			$("#search_tool_msg").text(default_search_tool_msg);		
		}
		
		lock_search_process = 0;
		
		$(str_element).focus();
		$(str_element).select();
	}
}	
