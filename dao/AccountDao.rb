require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/Account"

class AccountDao < DaoBase
  @@version = 0.02

  # 指定されたアカウント名のアカウント情報を返す
  def get_account_by_name(account_name)
    account = Account.new
    
    res = @db.exec(<<-"SQL")
      SELECT
        id, name, data_password, show_ratings_flag, image_url
      FROM
        accounts
      WHERE
        name = #{s account_name}
        AND del_flag = 0
    SQL
    
    if res.num_tuples != 1 then
      res.clear
      res_status = "Status: 400 Bad Request\n"
      res_body = "該当アカウントは登録されていません\n"
      raise "該当アカウントは登録されていません"
    else
      res.num_fields.times do |i|
        account.instance_variable_set("@#{res.fields[i]}", res[0][i])
      end
      res.clear
    end
    
    return account
  end
  
  # 指定された画像URLで更新する
  def update_image_url(account_name, image_url)
    account = Account.new

    res = @db.exec(<<-"SQL")
      UPDATE
        accounts
      SET
        image_url = #{image_url ? s(image_url) : "null"},
        lock_version = lock_version + 1,
        updated_at = CURRENT_TIMESTAMP
      WHERE
        name = #{s account_name}
      RETURNING
        id, name, image_url
    SQL
    
    if res.num_tuples != 1 then
      res.clear
      raise "該当アカウントは登録されていません(#{account_name})"
    else
      res.num_fields.times do |i|
        account.instance_variable_set("@#{res.fields[i]}", res[0][i])
      end
      res.clear
    end
    
    return account
  end
  
  # 指定されたアカウントの画像更新要求フラグを更新する
  def update_renew_image_url_flag(account_name, is_renew_image_url)
    account = Account.new

    res = @db.exec(<<-"SQL")
      UPDATE
        accounts
      SET
        renew_image_url_flag = #{is_renew_image_url ? 1 : 0},
        lock_version = lock_version + 1,
        updated_at = CURRENT_TIMESTAMP
      WHERE
        name = #{s account_name}
      RETURNING
        id, name, renew_image_url_flag
    SQL
    
    if res.num_tuples != 1 then
      res.clear
      raise "該当アカウントは登録されていません(#{account_name})"
    else
      res.num_fields.times do |i|
        account.instance_variable_set("@#{res.fields[i]}", res[0][i])
      end
      res.clear
    end
  end
    
end
