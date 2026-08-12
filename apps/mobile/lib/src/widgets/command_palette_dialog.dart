import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/search_result.dart';
import '../services/search_service.dart';

Future<void> showCommandPalette({
  required BuildContext context,
  required void Function(String target) onOpenTarget,
}) {
  return showDialog<void>(
    context: context,
    barrierColor: Colors.black54,
    builder: (_) => CommandPaletteDialog(onOpenTarget: onOpenTarget),
  );
}

class CommandPaletteDialog extends StatefulWidget {
  const CommandPaletteDialog({required this.onOpenTarget, super.key});

  final void Function(String target) onOpenTarget;

  @override
  State<CommandPaletteDialog> createState() => _CommandPaletteDialogState();
}

class _CommandPaletteDialogState extends State<CommandPaletteDialog> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();
  final _service = SearchService();
  Timer? _debounce;
  List<SirisSearchResult> _results = const [];
  int _highlighted = 0;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _focusNode.requestFocus();
    HardwareKeyboard.instance.addHandler(_handleGlobalKey);
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_handleGlobalKey);
    _debounce?.cancel();
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  bool _handleGlobalKey(KeyEvent event) {
    if (event is! KeyDownEvent) return false;
    if (event.logicalKey == LogicalKeyboardKey.escape) {
      Navigator.pop(context);
      return true;
    }
    if (_results.isEmpty) return false;
    if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
      setState(() => _highlighted = (_highlighted + 1) % _results.length);
      return true;
    }
    if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
      setState(
        () => _highlighted =
            (_highlighted - 1 + _results.length) % _results.length,
      );
      return true;
    }
    return false;
  }

  void _changed(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () => _search(value));
  }

  Future<void> _search(String value) async {
    final query = value.trim();
    if (query.length < 2) {
      if (mounted) {
        setState(() {
          _results = const [];
          _highlighted = 0;
          _loading = false;
          _error = null;
        });
      }
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await _service.search(query);
      if (mounted && _controller.text.trim() == query) {
        setState(() {
          _results = results;
          _highlighted = 0;
          _loading = false;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = error.toString();
        });
      }
    }
  }

  IconData _icon(String module) => switch (module) {
        'homelab' => Icons.dns_rounded,
        'running' => Icons.directions_run_rounded,
        'gym' => Icons.fitness_center_rounded,
        'activity' => Icons.notifications_rounded,
        'knowledge' => Icons.menu_book_rounded,
        'projects' => Icons.folder_rounded,
        'engineering' => Icons.engineering_rounded,
        'siris' => Icons.auto_awesome_rounded,
        _ => Icons.search_rounded,
      };

  void _open(SirisSearchResult result) {
    Navigator.pop(context);
    widget.onOpenTarget(result.target);
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      alignment: Alignment.topCenter,
      insetPadding: const EdgeInsets.only(top: 96, left: 20, right: 20),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640, maxHeight: 480),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                autofocus: true,
                decoration: const InputDecoration(
                  icon: Icon(Icons.search_rounded),
                  border: InputBorder.none,
                  hintText: 'Search SirisOS… (Esc to close)',
                ),
                onChanged: _changed,
                onSubmitted: (_) {
                  if (_results.isNotEmpty) _open(_results[_highlighted]);
                },
              ),
            ),
            const Divider(height: 1),
            if (_loading) const LinearProgressIndicator(),
            Flexible(
              child: Builder(
                builder: (context) {
                  if (_error != null) {
                    return Padding(
                      padding: const EdgeInsets.all(20),
                      child: Text(_error!, textAlign: TextAlign.center),
                    );
                  }
                  if (_controller.text.trim().length < 2) {
                    return const Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'Type at least 2 characters to search Knowledge, Projects, '
                        'Engineering, Siris Memory and more.',
                        textAlign: TextAlign.center,
                      ),
                    );
                  }
                  if (!_loading && _results.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.all(24),
                      child: Text('No matching SirisOS items found.'),
                    );
                  }
                  return ListView.builder(
                    shrinkWrap: true,
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    itemCount: _results.length,
                    itemBuilder: (context, index) {
                      final result = _results[index];
                      final selected = index == _highlighted;
                      return Material(
                        color: selected
                            ? Theme.of(context).colorScheme.primaryContainer
                            : Colors.transparent,
                        child: ListTile(
                          leading: Icon(_icon(result.module)),
                          title: Text(result.title),
                          subtitle: Text(
                            result.subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onTap: () => _open(result),
                          onFocusChange: (focused) {
                            if (focused) setState(() => _highlighted = index);
                          },
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
