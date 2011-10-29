class AccountProfile
	attr_accessor(
		:id,
		:account_id,
		:profile_property_id,
		:is_visible,
		:value,
		:uri,
		:created_at,
		:updated_at,
		:lock_version,
		# ProfileProperties
		:is_unique,
		:name,
		:display_name,
		# ProfileClasses
		:class_id,
		:class_display_name
	)
end
