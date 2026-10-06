/*
	Fire hydrant that still gives water (D61, ROADMAP idea 17): behaves as a vanilla well
	(4_world/entities/building/well.c: IsWell, WELL water source, ActionDrinkWellContinuous
	actiondrinkwellcontinuous.c:50, bottle filling, hand washing). About a third of the hydrants
	placed by sky_layout.py are this class (streets.furniture.wet); the rest are Land_SKY_Hydrant_Dry.
	Clean water like a well (P18: decide whether hydrants should carry a disease chance).
*/
class Land_SKY_Hydrant_Wet extends Well
{
}
