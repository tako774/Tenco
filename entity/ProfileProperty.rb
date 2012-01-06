class ProfileProperty
	attr_accessor(
		:id,
		:name,
		:profile_class_id,
		:is_unique,
		:created_at,
		:updated_at,
		:lock_version,
		:display_name,
		# Profile “o˜^—p
		:is_registered,
		# Profile Class
		:class_name,
		:class_display_name
	)
end
