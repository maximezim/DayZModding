// SKY_Skyline scripts. Module layout follows Bohemia's DayZ-Samples (Test_Crafting CfgMods).
class CfgPatches
{
	class SKY_Skyline_Scripts
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data"};
	};
};

class CfgMods
{
	class SKY_Skyline
	{
		type = "mod";
		class defs
		{
			class gameScriptModule
			{
				value = "";
				files[] = {"SKY_Skyline/sky_scripts/scripts/3_Game"};
			};
			class worldScriptModule
			{
				value = "";
				files[] = {"SKY_Skyline/sky_scripts/scripts/4_World"};
			};
			class missionScriptModule
			{
				value = "";
				files[] = {"SKY_Skyline/sky_scripts/scripts/5_Mission"};
			};
		};
	};
};
