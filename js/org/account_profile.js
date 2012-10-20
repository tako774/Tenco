lock_process = 0;   // プロセスのロック

// アカウントデータ表示
function get_profiles(account_name, account_password) {
	var account_name = account_name;
	var account_password = account_password;
	
	if (lock_process == 0) {
		// 実行ロック
		lock_process = 1;
		
		// 実行中表示
		$("#account_password").attr("disabled", "disabled");
		$("#get_profiles").css("display", "none");
		$("#message").text("プロフィール情報取得中...");

		// アカウント情報取得
		exec_get_profiles(account_name, account_password);
		
		// 実行ロック解除
		lock_process = 0;
	}
	
}

// 現在のアカウント情報表示
function exec_get_profiles(account_name, account_password) {
	var account_name = account_name;
	var account_password = account_password;
	
	$.ajax({
		type: "POST",
		url: "http://" + location.host + "/api/account_profile_select.cgi",
		data: {
			account_name: account_name,
			account_password: account_password
		},
		cache: false,
		dataType: "xml",
		success: function(data) {
			// 取得データ表示
			var profiles   = $("profile", $("account", $("account_profiles", data)));
			var profile_classes = $("profile_classes", $("account_profiles", data));
			
			// 登録用プロパティ選択リスト:optgroup 追加
			profile_classes.each(function() {
				var optgroup_html = 
					"<optgroup id=\"property_class_" + $("class_name", $(this)).text() + "\"" + 
					" label=\"" + $("class_display_name", $(this)).text() + "\">" +
					"</optgroup>";
				$("#property_name").append(optgroup_html);
				
				var optgroup_hidden_html = 
					"<optgroup id=\"property_class_hidden_" + $("class_name", $(this)).text() + "\"" + 
					" label=\"" + $("class_display_name", $(this)).text() + "\">" +
					"</optgroup>";
				$("#property_name_hidden").append(optgroup_hidden_html);
			});
			
			// 登録用プロパティ選択リスト:option 追加
			profile_classes.each(function() {
				var properties = $("property", $(this));
				var class_name = $("class_name", $(this)).text();
				
				properties.each(function() {
					var option_html = 
						"<option id=\"property_name_"+ $("name", $(this)).text() + "\" " + 
							"value=\"" + $("name", $(this)).text() + "\">" +
							$("display_name", $(this)).text() +
						"</option>";
						
					// ひとつしか登録できず、なおかつ登録済みのプロパティはリストに載せない
					if (
							$("is_registered", $(this)).text() == 1 &&
							$("is_unique", $(this)).text() == 1
					) {
						$("#property_class_hidden_" + class_name).append(option_html);
					} else {
						$("#property_class_" + class_name).append(option_html);
					}
				});
			});
			
			// 現在のプロフィール表示
			profiles.each(function() {
				var id = $("id", $(this)).text();
				var name = $("name", $(this)).text();
				var display_name = $("display_name", $(this)).text();
				var value = $("value", $(this)).text();
				var uri = $("uri", $(this)).text();
				var visibility = $("visibility", $(this)).text();
				
				add_current_profile_row(
					account_name,
					account_password,
					id,
					{
						name: name,
						display_name: display_name,
						value: value,
						uri: uri,
						visibility: visibility
					}
				)
			});
			
			// プロフィール設定エリア表示
			$("#profile_settings").css("display", "block");
			// メッセージ表示
			$("#message").text("現在の設定を取得しました（" + getTimeStr(new Date()) + "）");
		},
		error: function() {
			// エラーメッセージ表示
			$("#message").text("アカウント認証失敗！");
			// 入力エリア再表示
			$("#account_password").removeAttr("disabled");
			$("#get_profiles").css("display", "inline");
			// パスワード欄にフォーカス
			$("#account_password").focus();
			$("#account_password").select();
		}
	});
}

// 現在のプロフィールに行追加
function add_current_profile_row(
	account_name,
	account_password,
	id,
	property_data
) {
	$("#current_profile_data").append(
		"<tr id=\"" + id +"\">" +
		"<td id=\"property_display_name_" + id + "\">" + property_data.display_name + "</td>" + 
		"<td><input type=\"hidden\" id=\"property_value_" + id + "\" value=\"" +
			property_data.value + "\"></input>" + property_data.value + "</td>" +
		"<td class=\"uri suppli\"><input type=\"hidden\" id=\"property_uri_"   + id + "\" value=\"" +
			property_data.uri + "\"></input>" + property_data.uri + "</td>" +
		"<td><input type=\"checkbox\" id=\"property_visibility_" + id + "value=\"1\"" + 
			(property_data.visibility == "1" ? " checked=\"checked\"" : "") + " disabled=\"disabled\"></input></td>" +
		"<td><button type=\"button\" id=\"delete_profile_" + id + "\">削除</button></td>" +
		"</tr>"
	);
	
	// テキスト欄選択時に全文フォーカス
	$("#property_value_" + id).focus(function() { $(this).select();} );
	$("#property_uri_" + id).focus(function() { $(this).select();} );
	
	// 削除ボタンにアクション追加
	$("#delete_profile_" + id).click(function() {
		delete_profile(account_name, account_password, id, property_data);
	});
	
}

// プロフィールデータ登録
function add_profile(account_name, account_password, property_data) {
	var account_name = account_name;
	var account_password = account_password;
	var property_data = property_data;
	
	if (lock_process == 0) {
		// 実行ロック
		lock_process = 1;
		
		// 実行中表示
		var style = $("#add_profile").css("display");
		$("#add_profile").css("display", "none");
		$("#message").text("プロフィール情報登録中...");

		// アカウント情報取得
		exec_add_profile(account_name, account_password, property_data);
		
		// 実行ロック解除
		lock_process = 0;
		
		// 登録ボタン再有効化
		$("#add_profile").css("display", style);
	}
	
}

// プロフィールデータ登録実行
function exec_add_profile(account_name, account_password, property_data) {
	var account_name = account_name;
	var account_password = account_password;
	var property_data = property_data;
	
	$.ajax({
		type: "POST",
		url: "http://" + location.host + "/api/account_profile.cgi",
		data: {
			account_name: account_name,
			account_password: account_password,
			property_name: property_data.name,
			property_value: property_data.value,
			property_uri: property_data.uri,
			property_visibility: property_data.visibility
		},
		cache: false,
		dataType: "xml",
		success: function(data) {
			var profile = $("profile", $("account", $("account_profile", $(data))));
			var id = $("id", $(profile)).text();
			var is_unique = $("is_unique", $(profile)).text();
			
			// 登録済みプロフィール行に追加
			add_current_profile_row(
				account_name,
				account_password,
				id,
				property_data
			);
			
			// アカウントごとにひとつだけ登録できるプロパティだった場合
			// プロフィール追加可能な属性から削除
			if (is_unique == "1") {
				var class_name = $("#property_name_" + property_data.name).parent().get(0).id.replace("property_class_", "");
				$("#property_name_" + property_data.name).remove().appendTo($("#property_class_hidden_" + class_name));
			}
			
			// 登録領域の初期化
			$("#property_value").val("");
			$("#property_uri").val("");
			$("#property_visibility").attr("checked", "checked");
			
			// メッセージ表示
			$("#message").text("登録しました（" + getTimeStr(new Date()) + "）");
		},
		error: function(xhr) {
			// エラーメッセージ表示
			$("#message").text("登録失敗！（" + getTimeStr(new Date()) + "）\n" + xhr.responseText);
		}
	});
}

function delete_profile(account_name, account_password, account_profile_id, property_data) {
	var account_profile_id = account_profile_id;
	
	if (lock_process == 0) {
		// 実行ロック
		lock_process = 1;
		
		// 実行中表示
		$("#message").text("プロフィール情報削除中...");

		// プロフィール削除実行
		exec_delete_profile(account_name, account_password, account_profile_id, property_data);
		
		// 実行ロック解除
		lock_process = 0;
	}
}

function exec_delete_profile(account_name, account_password, account_profile_id, property_data) {
	
	$.ajax({
		type: "POST",
		url: "http://" + location.host + "/api/account_profile_delete.cgi",
		data: {
			account_name: account_name,
			account_password: account_password,
			account_profile_id: account_profile_id
		},
		cache: false,
		dataType: "string",
		success: function(data) {
			
			// 登録済みプロフィール行から削除
			$("#" + account_profile_id).remove();
			
			// プロフィール追加可能な属性として有効化
			var class_name = $("#property_name_" + property_data.name).parent().get(0).id;
			if (class_name.match(/property_class_hidden_/)) {
				class_name = class_name.replace("property_class_hidden_", "");
				$("#property_name_" + property_data.name).remove().appendTo($("#property_class_" + class_name));
			}
			
			// メッセージ表示
			$("#message").text("削除しました（" + getTimeStr(new Date()) + "）");
		},
		error: function(xhr) {
			// エラーメッセージ表示
			$("#message").text("削除失敗！（" + getTimeStr(new Date()) + "）\n" + xhr.responseText);
		}
	});
}
