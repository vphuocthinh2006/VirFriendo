extends Node
## Attach to a small test scene: press Space to call /game/external/decide (stub state/actions).
## Set `bearer_token` on the child GodotAiBridge (Inspector) after logging into the web app.
## Child node must be named exactly "GodotAiBridge".

@export var game_id: String = "source_of_mana"

@onready var bridge: GodotAiBridge = $GodotAiBridge


func _ready() -> void:
	if bridge == null:
		push_error("[CompanionAi] No child node named 'GodotAiBridge'. Add a child Node, attach godot_ai_bridge.gd, name it GodotAiBridge.")
	else:
		bridge.decide_ready.connect(_on_decide)
		bridge.decide_failed.connect(_on_fail)
		print("[CompanionAi] Test runner ready — press Space (ui_accept) to call /game/external/decide.")
		print("[CompanionAi] Using api_base_url=", bridge.api_base_url, " (set bearer_token on GodotAiBridge if API returns 401).")


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"):
		print("[CompanionAi] ui_accept received, sending request...")
		_run_stub()


func _run_stub() -> void:
	if bridge == null:
		push_warning("CompanionAiTestRunner: missing GodotAiBridge child")
		return
	var state := {"tick": Time.get_ticks_msec(), "stub": true}
	var actions := PackedStringArray(["wait", "attack_light", "move_north"])
	bridge.request_decide(game_id, state, actions, "neutral", false)


func _on_decide(action: String, source: String) -> void:
	print("[CompanionAi] action=", action, " source=", source)


func _on_fail(msg: String) -> void:
	print("[CompanionAi] FAILED: ", msg)
	push_warning("[CompanionAi] " + msg)
