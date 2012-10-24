require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/AccountExServiceAccount"

class AccountExServiceAccountDao < DaoBase
  @@version = 0.01
  
  # アカウントがもつ外部サービスアカウント情報を登録
  def insert(account_ex_service_account)
    new_entity = AccountExServiceAccount.new
    
    res = @db.exec(<<-"SQL")
      INSERT INTO
        account_ex_service_accounts (
          account_id
        , ex_service_account_id
        )
      VALUES (
        #{account_ex_service_account.account_id.to_i}
      , #{account_ex_service_account.ex_service_account_id.to_i}
      )
      RETURNING
        *
    SQL
    
    res.num_fields.times do |i|
      new_entity.instance_variable_set("@#{res.fields[i]}", res[0][i])
    end
    
    return new_entity
  end

  # アカウントID・外部サービスID・アカウントキーを元に削除
  def delete_by_ex_service_id_account_key(account_id, ex_service_id, account_key)
    entity = AccountExServiceAccount.new
    
    res = @db.exec(<<-"SQL")
      DELETE FROM
        account_ex_service_accounts
      WHERE
          account_id = #{account_id.to_i}
      AND ex_service_account_id = (
            SELECT
              id
            FROM
              ex_service_accounts
            WHERE
                  ex_service_id = #{ex_service_id.to_i}
              AND account_key = #{s account_key}
            )
      RETURNING
        *
    SQL
    
    res.num_fields.times do |i|
      entity.instance_variable_set("@#{res.fields[i]}", res[0][i])
    end
    
    return entity
  end
end
