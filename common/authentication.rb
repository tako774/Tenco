require "#{File.dirname __FILE__}/db"
require "#{File.dirname __FILE__}/utils"
include Utils
require "#{File.dirname __FILE__}/cryption"
require "#{File.dirname __FILE__}/../entity/Account"

# 認証クラス
class Authentication
	VERSION = 'v0.07'

	# salt を取得
	# プライベートクラスメソッド 通常はパスワード無しで salt を公開しないこと
	def self.get_salt(name)
	
		# DB接続取得
		db = DB.getInstance
		
		# DB検索で salt を取得
		res_salt = db.exec(<<-"SQL")
		  SELECT
		    data_password
		  FROM
		    accounts
		  WHERE
		    name = #{s name}
		    AND del_flag = 0
		  OFFSET 0 LIMIT 1
		  ;
		SQL
		
		# 検索結果があれば返す
		unless res_salt.num_tuples == 1 then
			return nil
		else
			return res_salt[0][0]
		end
		
		res_salt.clear
	end
	private_class_method :get_salt
	
	# アカウント認証
	# 成功するとDBアカウントレコードを返す
	# 失敗すると例外を発生させる
	def self.login(name, password)
		
		# ソルト文字列取得
		salt = get_salt(name)
		raise "エラー：アカウント認証に失敗しました。salt が見つかりません（#{name}）" unless salt
		
		# DB接続取得
		db = DB.getInstance
		
		# DB検索でパスワード一致するアカウント情報を取得
		res = db.exec(<<-"SQL")
		  SELECT
		    id,
		    name,
		    data_password,
		    del_flag,
		    mail_address,
		    show_ratings_flag,
		    allow_edit_profile,
		    lock_version
		  FROM
		    accounts
		  WHERE
		    name = #{s name}
			AND password = #{s Cryption.stored_password(password, salt)}
			AND del_flag = 0
		  OFFSET 0 LIMIT 1
		  ;
		SQL
		
		# 検索結果があればOK
		unless res.num_tuples == 1 then
			res.clear
			begin
				require 'socket'
				host_name = ""
				host_name = Socket.gethostbyaddr((ENV['REMOTE_ADDR'].split('.').collect {|x| x.to_i}).pack('C4'))[0]
			rescue
				host_name = ENV['REMOTE_ADDR']
			end
			raise "エラー：アカウント認証に失敗しました。（#{name}, #{host_name}）"
		else
			account = Account.new
			res.num_fields.times do |i|
				account.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
			res.clear
			return account
		end
	end

	# アカウント新規登録
	# なければ作成、あればエラー
	def self.register(name, raw_password, mail_address)
		
		# データパスワード兼saltの生成
		salt_length = 16  # データ出力時の暗号鍵のオクテット文字列長
		salt = Cryption.mk_octet_str(salt_length)
		
		# DB接続取得
		db = DB.getInstance
		
		# DBに登録
		res = db.exec(<<-"SQL")
		  INSERT INTO accounts (
			name,
			password,
			mail_address,
			data_password
		  )
		  VALUES (
		    #{s name},
			#{s Cryption.mk_stored_password(raw_password, salt)},
			#{s Cryption.stored_mail_address(mail_address, salt)},
			#{s salt}
		  ) RETURNING *;
		SQL
		
		# 登録結果があればOK
		unless res.num_tuples == 1 then
			res.clear
			raise "エラー：アカウントの新規登録に失敗しました。"
		else
			res.clear
			return nil
		end
	end
	
	# アカウント情報更新
	# なければエラー
	def self.update(name, password, new_mail_address, new_raw_password, show_ratings_flag, allow_edit_profile, lock_version)
		
		# ソルト文字列取得
		salt = get_salt(name)
		raise "エラー：アカウント認証に失敗しました。salt が見つかりません（#{name}）" unless salt

		# DB接続取得
		db = DB.getInstance
		
		# DBに登録
		sql = <<-"SQL"
		  UPDATE 
			accounts
		  SET
			#{"password = " + s(Cryption.mk_stored_password(new_raw_password, salt)) + "," if new_raw_password}
			#{"mail_address = " + s(Cryption.stored_mail_address(new_mail_address, salt)) + ","  if new_mail_address}
			#{"show_ratings_flag = " + show_ratings_flag.to_i.to_s + ","  if show_ratings_flag}
			#{"allow_edit_profile = " + allow_edit_profile.to_i.to_s + ","  if allow_edit_profile}
			lock_version = lock_version + 1,
			updated_at = CURRENT_TIMESTAMP
		  WHERE
			name = #{s name}
			AND password = #{s Cryption.stored_password(password, salt)}
			AND del_flag = 0
			AND lock_version = #{lock_version.to_i}
		  RETURNING *;
		SQL

		res = db.exec(sql)
		
		# 登録結果があればOK
		unless res.num_tuples == 1 then
			res.clear
			begin
				require 'socket'
				host_name = ""
				host_name = Socket.gethostbyaddr((ENV['REMOTE_ADDR'].split('.').collect {|x| x.to_i}).pack('C4'))[0]
			rescue
				host_name = ENV['REMOTE_ADDR']
			end
			raise "エラー：アカウントの更新に失敗しました。（#{host_name}）\n#{sql}"
		else
			account = Account.new
			res.num_fields.times do |i|
				account.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
			res.clear
			return account
		end
	end
	
	# アカウント削除(パスワードありの場合)
	# 成功するとDBアカウントレコードを返す
	# 失敗すると例外を発生させる
	def self.delete(name, password)
		
		# ソルト文字列取得
		salt = get_salt(name)
		raise "エラー：アカウント認証に失敗しました。salt が見つかりません（#{name}, #{host_name}）" unless salt

		# DB接続取得
		db = DB.getInstance
		
		# アカウント削除SQL実行
		sql = <<-"SQL"
		  UPDATE
		    accounts
		  SET
		    del_flag = 1,
		    password = NULL,
		    mail_address = NULL,
		    lock_version = lock_version + 1,
			updated_at = CURRENT_TIMESTAMP
		  WHERE
			name = #{s name}
			AND password = #{s Cryption.stored_password(password, salt)}
			AND del_flag = 0
		  RETURNING *;
		SQL
		
		res = db.exec(sql)
		
		# 更新がなければエラー
		unless res.num_tuples == 1 then
			res.clear
			begin
				require 'socket'
				host_name = ""
				host_name = Socket.gethostbyaddr((ENV['REMOTE_ADDR'].split('.').collect {|x| x.to_i}).pack('C4'))[0]
			rescue
				host_name = ENV['REMOTE_ADDR']
			end
			raise "エラー：アカウントの削除に失敗しました。（#{name}, #{host_name}）"
		end
		
		account = Account.new
		res.num_fields.times do |i|
			account.instance_variable_set("@#{res.fields[i]}", res[0][i])
		end
		res.clear
		return account
		
	end
	
	# アカウント削除(生パスワードの場合)
	# 成功するとDBアカウントレコードを返す
	# 失敗すると例外を発生させる
	def self.delete_by_raw_password(name, raw_password)
		delete name, Cryption.hash_as_client(raw_password)
	end
end
