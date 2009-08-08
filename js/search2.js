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
			before_str = str;
			var $targets = $(target_element);
				
			// IEの場合は一度に検索
			if (jQuery.browser.msie) {
				if (str != "") {
					$targets.each(function() {
						if (str == "" || $(this).text().indexOf(str) != -1) {
							$(this).show();
						}
						else {
							$(this).hide();
						}
					});
				}
				else {
					$targets.show();
				}
				
				$(str_element).focus();
				$(str_element).select();
				lock_search_process = 0;
			}
			else {
				var default_serach_tool_msg = $("#search_tool_msg").text();
				$targets.css("display", "none");
				
				if (str != "") {
					loop(
						{
							begin: 0,
							end: $targets.length,
							step: 1000
						},
						function (n, o) {
							$targets.slice(n, n + o.step).each(
								function() {
									$("#search_tool_msg").text(n + "/" + $targets.length + " 検索中");
									
									if (str == "" || $(this).text().indexOf(str) != -1) {
										// IE 以外は css の display を操作するほうが体感高速 
										$(this).css("display", display_style);
									}
								}
							);
						}
					).next(
						function() {
							$("#search_tool_msg").text(default_serach_tool_msg);							
							
							$(str_element).focus();
							$(str_element).select();
							lock_search_process = 0;
						}
					);
				}
				else {
					// IE 以外は css の display を操作するほうが体感高速 
					$targets.css("display", display_style);
					
					$(str_element).focus();
					$(str_element).select();
					lock_search_process = 0;
				}
			}
		}
		else {
			lock_search_process = 0;
		}
	}
}	
