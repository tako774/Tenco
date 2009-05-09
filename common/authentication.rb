require 'db'
require 'utils'
include Utils
require 'Account'

# 認証クラス
class Authentication
	VERSION = 'v0.02'

	# アカウント認証
	# 成功するとDBアカウントレコードを返す
	# 失敗すると例外を発生させる
	def self.login (name, password)
		
		# DB接続取得
		db = DB.getInstance
		
		# DB検索
		res = db.exec(<<-"SQL")
		  SELECT
		    id, name, data_password, del_flag, encrypted_mail_address, show_ratings_flag, lock_version
		  FROM
		    accounts
		  WHERE
		    name = #{s name}
			AND password = #{s password}
			AND del_flag = 0
		  OFFSET 0 LIMIT 1
		  ;
		SQL
		
		# 検索結果があればOK
		unless res.num_tuples == 1 then
			res.clear
			raise "エラー：アカウント認証に失敗しました。"
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
	def self.register (name, password, mail_address)
		require 'cryption'
		
		data_password_length = 16  # データ出力時の暗号鍵のオクテット文字列長
		
		# DB接続取得
		db = DB.getInstance
		
		# DBに登録
		res = db.exec(<<-"SQL")
		  INSERT INTO accounts (
			name,
			password,
			encrypted_password,
			encrypted_mail_address,
			data_password
		  )
		  VALUES (
		    #{s name},
			#{s Cryption.hash(password)},
			#{s Cryption.encrypt(password)},
			#{s Cryption.encrypt(mail_address)},
			#{s Cryption.mk_octet_str(data_password_length)}
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
	def self.update (name, password, new_mail_address, new_password, show_ratings_flag, lock_version)
		require 'cryption'
		
		# DB接続取得
		db = DB.getInstance
		
		# DBに登録
		sql = <<-"SQL"
		  UPDATE 
			accounts
		  SET
			#{"password = " + s(Cryption.hash(new_password)) + "," if new_password}
			#{"encrypted_password = " + s(Cryption.encrypt(new_password)) + "," if new_password}
			#{"encrypted_mail_address = " + s(Cryption.encrypt(new_mail_address)) + ","  if new_mail_address}
			#{"show_ratings_flag = " + show_ratings_flag.to_i.to_s + ","  if show_ratings_flag}
			lock_version = lock_version + 1,
			updated_at = CURRENT_TIMESTAMP
		  WHERE
			name = #{s name}
			AND password = #{s password}
			AND del_flag = 0
			AND lock_version = #{lock_version.to_i}
		  RETURNING *;
		SQL

		res = db.exec(sql)
		
		# 登録結果があればOK
		unless res.num_tuples == 1 then
			res.clear
			raise "エラー：アカウントの更新に失敗しました。\n#{sql}"
		else
			account = Account.new
			res.num_fields.times do |i|
				account.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
			res.clear
			return account
		end
	end
end
