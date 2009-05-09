// アカウントデータ表示
function get_account_settings(account_name, account_password) {
	var account_name = account_name;
	var account_password = account_password;
	
	if (lock_account_process == 0) {
		// 実行ロック
		lock_account_process = 1;
		
		// 実行中表示
		$("#account_password").attr("disabled", "disabled");
		$("#get_settings").css("display", "none");
		$("#message").text("アカウント情報取得中...");		

		// アカウント情報取得
		show_account_settings(account_name, account_password);
		
		// 実行ロック解除
		lock_account_process = 0;
	}
	
}

// アカウントデータ更新
function update_account_settings(account_name, account_password, new_mail_address, new_account_password, new_show_ratings_flag, lock_version) {
	var account_name          = account_name;
	var account_password      = account_password;
	var new_mail_address      = new_mail_address;
	var new_account_password  = new_account_password;
	var new_show_ratings_flag = new_show_ratings_flag;
	var lock_version          = lock_version;
	
	if (lock_account_process == 0) {
		// 実行ロック
		lock_account_process = 1;
		
		// 実行中表示
		$("#update_settings").css("display", "none");
		$("#message").text("アカウント情報更新中...");		

		// アカウント情報更新
		update_account_settings(account_name, account_password, new_mail_address, new_account_password, new_show_ratings_flag, lock_version);
		
		// 実行ロック解除
		lock_account_process = 0;
	}
	
}

// 現在のアカウント情報表示
function show_account_settings(account_name, account_password) {
	var account_name = account_name;
	var account_password = account_password;
	
	var mail_address = "";
	
	$.ajax({
		type: "POST",
		url: "http://tenco.xrea.jp/api/account_select.cgi",
		data: {
			account_name: account_name,
			account_password: account_password
		},
		cache: false,
		dataType: "xml",
		success: function(data) {
			// 取得データ表示
			var mail_address = $("mail_address", $("account", data)).text();
			var show_ratings_flag = $("show_ratings_flag", $("account", data)).text();
			var lock_version = $("lock_version", $("account", data)).text();
			
			if (mail_address) {
				$("#mail_address").text(mail_address);
				$("#new_mail_address").val(mail_address);
			}
			else {
				$("#mail_address").text("＜未設定＞");
			}
			
			if (show_ratings_flag == 0) {
				$("#show_ratings").text("あいまい表示");
				$("input[@name='new_show_ratings_flag'][value='0']").attr("checked", "checked");
				$("input[@name='new_show_ratings_flag'][value='1']").removeAttr("checked");
			}
			else {
				$("#show_ratings").text("表示する");
				$("input[@name='new_show_ratings_flag'][value='0']").removeAttr("checked");
				$("input[@name='new_show_ratings_flag'][value='1']").attr("checked", "checked");
			}
			
			$("#lock_version").val(lock_version);
			$("#account_settings").css("display", "block");
			
			// 設定更新ボタン表示
			$("#update_settings").css("display", "inline");
			// メッセージ表示
			$("#message").text("現在の設定を取得しました（" + getTimeStr(new Date()) + "）");
		},
		error: function() {
			// エラーメッセージ表示
			$("#message").text("アカウント認証失敗！");
			// 入力エリア再表示
			$("#account_password").removeAttr("disabled");
			$("#get_settings").css("display", "inline");
			// パスワード欄にフォーカス
			$("#account_password").focus();
			$("#account_password").select();
		}
	});
}

// アカウント情報更新
function update_account_settings(account_name, account_password, new_mail_address, new_account_password, new_show_ratings_flag, lock_version) {
	var account_name          = account_name;
	var account_password      = account_password;
	var new_mail_address      = new_mail_address;
	var new_account_password  = new_account_password;
	var new_show_ratings_flag = new_show_ratings_flag;
	var lock_version          = lock_version;	
	
	$.ajax({
		type: "POST",
		url: "http://tenco.xrea.jp/api/account_update.cgi",
		data: {
			account_name: account_name,
			account_password: account_password,
			new_mail_address: new_mail_address,
			new_account_password: new_account_password,
			new_show_ratings_flag: new_show_ratings_flag,
			lock_version: lock_version
		},
		cache: false,
		success: function(data) {
			// 取得データ表示
			var mail_address = $("mail_address", $("account", data)).text();
			var show_ratings_flag = $("show_ratings_flag", $("account", data)).text();
			var lock_version = $("lock_version", $("account", data)).text();
			
			if (mail_address) {
				$("#mail_address").text(mail_address);
				$("#new_mail_address").val(mail_address);
			}
			else {
				$("#mail_address").text("＜未設定＞");
			}
			
			if (show_ratings_flag == 0) {
				$("#show_ratings").text("あいまい表示");
				$("input[@name='new_show_ratings_flag'][value='0']").attr("checked", "checked");
				$("input[@name='new_show_ratings_flag'][value='1']").removeAttr("checked");
			}
			else {
				$("#show_ratings").text("表示する");
				$("input[@name='new_show_ratings_flag'][value='0']").removeAttr("checked");
				$("input[@name='new_show_ratings_flag'][value='1']").attr("checked", "checked");
			}
			$("#lock_version").val(lock_version);
			
			// パスワード更新
			if (new_account_password) {
				$("#account_password").val(new_account_password);
			}
			
			// メッセージ表示
			$("#message").text("設定を更新しました（" + getTimeStr(new Date()) + "）");
			// 設定更新ボタン表示
			$("#update_settings").css("display", "inline");
		},
		error: function(xhr) {
			// エラーメッセージ表示
			$("#message").text("更新失敗！（" + getTimeStr(new Date()) + "）\n" + xhr.responseText);
			// 入力エリア再表示
			$("#update_settings").css("display", "inline");
		}
	});
}
