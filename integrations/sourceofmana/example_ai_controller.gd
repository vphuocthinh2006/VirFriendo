extends Node2D
## Minimal pattern: when you have state + actions, ask the server and print the result.
## Replace with your player controller: call apply_action(action) on your game.

@onready var bridge: GodotAiBridge = $GodotAiBridge

func _ready() -> void:
	bridge.decide_ready.connect(_on_decide)
	bridge.decide_failed.connect(_on_fail)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"):
		_request_stub()


func _request_stub() -> void:
	var state := {
		"tick": Time.get_ticks_msec(),
		"stub": true,
	}
	var actions := PackedStringArray(["wait", "attack_light", "move_north"])
	bridge.request_decide("source_of_mana", state, actions, "neutral", false)


func _on_decide(action: String, source: String) -> void:
	print("[AI] action=%s source=%s" % [action, source])


func _on_fail(msg: String) -> void:
	push_warning("[AI] %s" % msg)
