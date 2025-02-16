# from gym.envs.registration import register
# from gym.envs.registration import registry

# env_dict = registry.env_specs.copy()


# ids = ["cookingEnv-v1", "cookingZooEnv-v0"]
# for id in ids:
#     if id in env_dict:
#         del registry.env_specs[id]
#         print("Remove {} from registry".format(id))
#     register(
#         id=id,
#         entry_point="gym_cooking.environment:GymCookingEnvironment"
#         if id == "cookingEnv-v1"
#         else "gym_cooking.environment:CookingZooEnvironment",
#     )


from gym.envs.registration import register

register(id="cookingEnv-v1", entry_point="gym_cooking.environment:GymCookingEnvironment")
register(id="cookingZooEnv-v0", entry_point="gym_cooking.environment:CookingZooEnvironment")
