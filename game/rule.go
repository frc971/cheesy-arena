// Copyright 2020 Team 254. All Rights Reserved.
// Author: pat@patfairbank.com (Patrick Fairbank)
//
// Model of a game-specific rule.

package game

type Rule struct {
	Id             int
	RuleNumber     string
	IsMajor        bool
	IsRankingPoint bool
	Description    string
}

// All rules from the 2022 game that carry point penalties.
// @formatter:off
var rules = []*Rule{
	// Conduct
	{1, "G206", false, true, "A team or ALLIANCE may not collude with another team to purposefully violate a rule to influence Ranking Points."},
	{2, "G210", true, false, "A strategy not consistent with standard gameplay and clearly aimed at forcing the opponent ALLIANCE to violate a rule is not allowed."},

	// Pre-MATCH
	{3, "G301", true, false, "A DRIVE TEAM member may not cause significant delays to the start of their MATCH."},

	// AUTO
	{4, "G401", false, false, "In AUTO, each DRIVE TEAM member must remain in their staged areas and may not contact anything in front of their HUMAN STARTING LINE (exceptions: safety, E-Stop/A-Stop, or REFEREE permission)."},
	{5, "G402", false, false, "In AUTO, a DRIVE TEAM member may not directly or indirectly interact with a ROBOT or OPERATOR CONSOLE (exceptions: safety or E-Stop/A-Stop)."},
	{6, "G403", true, false, "In AUTO, a ROBOT whose BUMPERS are completely across the CENTER LINE may not contact an opponent ROBOT."},

	// SCORING ELEMENTS
	{7, "G404", true, false, "A ROBOT may not deliberately use a SCORING ELEMENT to ease or amplify a challenge associated with a FIELD element."},
	{8, "G405", false, false, "A ROBOT may not intentionally eject SCORING ELEMENTS from the FIELD (exception: through the base of the OUTPOST)."},
	{9, "G405", true, false, "A ROBOT may not intentionally eject SCORING ELEMENTS from the FIELD (exception: through the base of the OUTPOST). Repeated violation."},
	{10, "G406", true, false, "Neither a ROBOT nor a HUMAN PLAYER may damage a SCORING ELEMENT."},

	// ROBOT
	{11, "G410", false, false, "ROBOT extensions may not interact with the carpet, BUMPS, or TOWER BASE such that BUMPERS are lifted out of the BUMPER ZONE."},
	{12, "G412", true, false, "A ROBOT may not grab, grasp, attach to, entangle with, or suspend from FIELD elements (exception: RUNGS and UPRIGHTS)."},
	{13, "G413", false, false, "A ROBOT may not extend beyond the horizontal or vertical expansion limits in R105, R106, and R107."},
	{14, "G413", true, false, "A ROBOT may not extend beyond the horizontal or vertical expansion limits in R105, R106, and R107. Strategic benefit violation."},

	// Opponent Interaction
	{15, "G415", false, false, "A ROBOT may not use a COMPONENT outside its ROBOT PERIMETER (except BUMPERS) to initiate contact with an opponent ROBOT inside the opponent's ROBOT PERIMETER."},
	{16, "G416", true, false, "A ROBOT may not damage or functionally impair an opponent ROBOT: A. deliberately, or B. by initiating contact inside the vertical projection of the opponent's ROBOT PERIMETER."},
	{17, "G417", true, false, "A ROBOT may not deliberately attach to, tip, or entangle with an opponent ROBOT."},
	{18, "G418", false, false, "A ROBOT may not PIN an opponent's ROBOT for more than 3 seconds."},
	{19, "G418", true, false, "A ROBOT may not PIN an opponent's ROBOT for more than 3 seconds. Escalating violation every 3 seconds."},
	{20, "G419", true, false, "2 or more ROBOTS working together may not isolate or close off any major element of MATCH play."},
	{21, "G420", true, false, "A ROBOT may not contact an opponent ROBOT in contact with an opponent TOWER during the last 30 seconds of the MATCH."},

	// Human
	{22, "G421", false, false, "DRIVE TEAM members must remain in their designated areas: DRIVERS/COACHES in the ALLIANCE AREA, HUMAN PLAYERS in the ALLIANCE AREA, TECHNICIANS in their designated area."},
	{23, "G422", true, false, "A ROBOT shall be operated only by the DRIVERS and/or HUMAN PLAYERS of that team (exception: DRIVE COACH E-Stop/A-Stop)."},
	{24, "G423", false, false, "A DRIVE TEAM member may not extend into the CHUTE beyond the ALLIANCE-colored tape line (when open) or into the CORRAL beyond the tape line."},
	{25, "G424", true, false, "A DRIVE TEAM member may not deliberately use a SCORING ELEMENT to ease or amplify a challenge associated with a FIELD element."},
	{26, "G425", true, false, "FUEL may only be introduced to the FIELD through the CHUTE, through the base of the OUTPOST, or thrown from the OUTPOST AREA."},
	{27, "G426", false, false, "DRIVE COACHES may not touch SCORING ELEMENTS, unless for safety purposes."},
	{28, "G427", false, false, "Off-FIELD FUEL may only be stored in the CHUTE and CORRAL. Excess FUEL must immediately be entered onto the FIELD."},
	{29, "G427", true, false, "Off-FIELD FUEL may only be stored in the CHUTE and CORRAL. Excess FUEL must immediately be entered onto the FIELD. Continuous violation."},
}

// @formatter:on
var ruleMap map[int]*Rule

// Returns the rule having the given ID, or nil if no such rule exists.
func GetRuleById(id int) *Rule {
	return GetAllRules()[id]
}

// Returns a slice of all defined rules that carry point penalties.
func GetAllRules() map[int]*Rule {
	if ruleMap == nil {
		ruleMap = make(map[int]*Rule, len(rules))
		for _, rule := range rules {
			ruleMap[rule.Id] = rule
		}
	}
	return ruleMap
}
