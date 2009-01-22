lock_show_user_data = 0;   // アカウント固有データ表示プロセスのロック

// アカウント固有データ表示
function show_user_data(account_name, account_password) {
	var account_name = account_name;
	var account_password = account_password;
	
	if (lock_show_user_data == 0) {
		// 実行ロック
		lock_show_user_data = 1;
		
		// 実行中表示
		$("#decrypt_tool").css("display", "none");
		$("#decrypt_tool_msg").text("通信中");		

		// 復号化
		decrypt(account_name, account_password);
	}
}

// データパスワード取得⇒成功時に復号化実行
function decrypt(account_name, account_password) {
	var account_name = account_name;
	var account_password = account_password;
	var data_password = "";
		
	$.ajax({
		type: "POST",
		url: "http://tenco.xrea.jp/api/account_data_password.cgi",
		data: {
			account_name: account_name,
			account_password: account_password
		},
		cache: true,
		dataType: "xml",
		success: function(data) {
			// データパスワード取得
			data_password = $("data_password", $("account", data)).text();
			// データ復号化
			decrypt_data(data_password);
		},
		error: function() {
			// プロセスロック解除
			lock_show_user_data = 0;
			// エラーメッセージ表示
			$("#decrypt_tool_msg").text("アカウント認証失敗！");
			// 入力エリア再表示
			$("#decrypt_tool").css("display", "inline");
			// パスワード欄にフォーカス
			$("#account_password").focus();
		}
	});
}

// 復号化関数
// enc クラス直下の text を URLデコード ⇒ base64デコード ⇒ aes-256-cbc(salt有)デコード
function decrypt_data(password) {
	var password = password;
	
	// 復号中メッセージ表示
	$("#decrypt_tool_msg").text("復号中");		
			
	// 復号化処理対象となる要素を取得
	var $encs = $(".enc");
	var $enc_alts = $(".enc_alt");		
	
	// 非同期ループ：復号化
	loop(
		{
			begin: 0,
			end: $encs.length,
			step: jQuery.browser.msie ? 100 : 10 // IE はあまりに遅すぎて結局動作が固まるので、ステップ数を大きくする
		},
		function (n, o) {
			$encs.slice(n, n + o.step).each(
				function() {
					$("#decrypt_tool_msg").text(n + "/" + $encs.length + " 復号中");
					try {
			  			$(this).text(
			  				GibberishAES.dec(Url.decode($(this).text()), password)
			  			);
			  			$(this).removeClass("enc");
					}
					catch(e) {
						$(this).text("Error : " + e);
					}
				}
				
			);
		}
	).next(
		function() {
			$("#decrypt_tool_msg").text("");
		}
	);

	$enc_alts.css("display", "none");
}
