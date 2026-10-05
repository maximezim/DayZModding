// Empty addon: registers a CfgPatches entry and nothing else.
// New-Mod.ps1 copies this folder and renames "ModTemplate" to your mod name.
class CfgPatches
{
    class ModTemplate_Scripts
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] = { "DZ_Data" };
    };
};

// When the mod gets scripts, declare the script modules here, following the
// vanilla layering (3_Game -> 4_World -> 5_Mission). Example shape:
//
// class CfgMods
// {
//     class ModTemplate
//     {
//         type = "mod";
//         dependencies[] = { "Game", "World", "Mission" };
//         class defs
//         {
//             class gameScriptModule    { value = ""; files[] = { "ModTemplate/scripts/3_Game" }; };
//             class worldScriptModule   { value = ""; files[] = { "ModTemplate/scripts/4_World" }; };
//             class missionScriptModule { value = ""; files[] = { "ModTemplate/scripts/5_Mission" }; };
//         };
//     };
// };
