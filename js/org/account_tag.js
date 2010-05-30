// プレイヤータグ取得
// 成功したかどうかを返す
var got_account_tags = false;
function get_account_tags(account_name) {
	var account_name = account_name;
	
	$("#account_tag_tool").hide();
	$("#account_tag_msg").text("最新タグ取得中");
	
	$.ajax({
		type: "GET",
		url: "http://" + location.host + "/api/account_tag_select.cgi",
		data: {
			account_name: account_name
		},
		cache: false,
		dataType: "xml",
		success: function(data) {
			// 取得データ表示
			var account = $("account", $("account_tags", data))
			var tags = $("tag", account);
			
			// 表示クリア
			$("#account_tags").empty();
			$("#account_tag_msg").text("（最新タグ情報取得済み）");
			
			// データ表示
			tags.each(function() {
				// Apache1.3 では AllowEncodeSlashes が使えず、%2f を文字列として扱えないのでデコードしておく
				$("#account_tags").append(
					"<li>" +
					"<a href=\"http://" + location.host + "/tag/" + urlDecode2f(encodeURIComponent(xmlUnescape($("display_name", $(this)).text()))) + "\">" + 
					$("display_name", $(this)).text() +
					"</a>" +
					"</li>"
				);
			});
			
			// 入力エリア再表示
			$("#account_tag_tool").show();
			
			got_account_tags = true;
		},
		error: function() {
			// 表示クリア
			$("#account_tags").empty();
			// エラーメッセージ表示
			$("#account_tag_msg").text("取得失敗");
		}
	});
	
}

// プレイヤータグ追加
function add_account_tag(account_name, tag_name) {
	var account_name  = account_name;
	var tag_name      = tag_name;	
	
	$("#account_tag_tool").hide();
	$("#account_tag_msg").text("登録中");
	
	$.ajax({
		type: "POST",
		url: "http://" + location.host + "/api/account_tag.cgi",
		data: {
			account_name: account_name,
			tag_name: tag_name 
		},
		cache: true,
		success: function(data) {
			// 表示変更
			var li = document.createElement('li');
			var a = document.createElement('a');
			// Apache1.3 では AllowEncodeSlashes が使えず、%2f を文字列として扱えないのでデコードしておく
			a.href = "http://" + location.host + "/tag/" + urlDecode2f(encodeURIComponent(tag_name));
			var txt = document.createTextNode(tag_name);
			
			a.appendChild(txt);
			li.appendChild(a);
			
			$("#account_tags").append(li);
			$("#account_tag_msg").text("登録成功（次回のページ更新後から、登録したタグが表示されます）");
		},
		error: function(xhr) {
			// エラーメッセージ表示
			$("#account_tag_msg").text("登録失敗！（" + getTimeStr(new Date()) + "）\n" + xhr.responseText);
		},
		complete : function() {
			// 入力エリア再表示
			$("#account_tag_tool").show();
		}
	});
}

// プレイヤータグ削除
function delete_account_tag(account_name, tag_name) {
	var account_name  = account_name;
	var tag_name      = tag_name;	
	
	$("#account_tag_tool").hide();
	$("#account_tag_msg").text("削除中");
	
	$.ajax({
		type: "POST",
		url: "http://" + location.host + "/api/account_tag_delete.cgi",
		data: {
			account_name: account_name,
			tag_name: tag_name 
		},
		cache: true,
		success: function(data) {
			// 表示変更
			$("#account_tags > li").each(function() {
				if ($(this).text() == tag_name) {
					$(this).remove();
				}
			});
			$("#account_tag_msg").text("削除成功（次回のページ更新後から、削除されたタグが見えなくなります）");
		},
		error: function(xhr) {
			// エラーメッセージ表示
			$("#account_tag_msg").text("削除失敗！（" + getTimeStr(new Date()) + "）\n" + xhr.responseText);
		},
		complete : function() {
			// 入力エリア再表示
			$("#account_tag_tool").show();
		}
	});
}

