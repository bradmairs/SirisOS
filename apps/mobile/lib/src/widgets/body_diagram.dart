import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../theme/app_theme.dart';

/// A hand-authored front/back body silhouette, split into the same six
/// muscle-group regions [GymService]/`MUSCLE_GROUPS` uses. Each region's
/// fill color is computed by the caller (see [MuscleMapCard]) and baked
/// into the SVG markup directly, rather than trying to recolor named paths
/// at render time -- flutter_svg has no first-class per-path theming API,
/// and generating the string ourselves keeps this self-contained (no
/// external asset to source or license).
///
/// The anatomical linework (ab segments, delt/pec/lat separation, muscle
/// striations) is purely decorative -- it's drawn on top of the same six
/// colored regions to read as a detailed muscle diagram, without implying
/// finer-grained data than the six tracked groups actually carry.
class BodyDiagram extends StatefulWidget {
  const BodyDiagram({
    required this.front,
    required this.colors,
    super.key,
  });

  final bool front;
  final Map<String, Color> colors;

  static const _neutral = AppTheme.surfaceRaised;

  @override
  State<BodyDiagram> createState() => _BodyDiagramState();
}

class _BodyDiagramState extends State<BodyDiagram> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late Map<String, Color> _previousColors;
  late Map<String, Color> _targetColors;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 600));
    // Fades in from neutral on first mount -- the same "reveal" treatment a
    // later color change gets, rather than popping straight to full color.
    _previousColors = {for (final group in widget.colors.keys) group: BodyDiagram._neutral};
    _targetColors = widget.colors;
    _controller.forward(from: 0);
  }

  @override
  void didUpdateWidget(covariant BodyDiagram oldWidget) {
    super.didUpdateWidget(oldWidget);
    // A front/back toggle re-reveals the newly-visible group (chest vs.
    // back) from neutral rather than blending shapes -- the two overlay
    // paths have different geometry, so morphing between them doesn't
    // produce a sensible in-between shape. An underlying fatigue-data
    // change instead animates smoothly from the last shown color.
    final viewChanged = oldWidget.front != widget.front;
    final colorsChanged = !_mapEquals(oldWidget.colors, widget.colors);
    if (!viewChanged && !colorsChanged) return;
    _previousColors = viewChanged
        ? {for (final group in widget.colors.keys) group: BodyDiagram._neutral}
        : _currentColors();
    _targetColors = widget.colors;
    _controller.forward(from: 0);
  }

  static bool _mapEquals(Map<String, Color> a, Map<String, Color> b) {
    if (a.length != b.length) return false;
    for (final entry in a.entries) {
      if (b[entry.key] != entry.value) return false;
    }
    return true;
  }

  Map<String, Color> _currentColors() {
    final t = Curves.easeOut.transform(_controller.value);
    return {
      for (final group in _targetColors.keys)
        group: Color.lerp(_previousColors[group] ?? BodyDiagram._neutral, _targetColors[group], t)!,
    };
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  static const _outline = AppTheme.border;

  static String _hex(Color color) {
    int byte(double v) => (v * 255).round().clamp(0, 255);
    final r = byte(color.r).toRadixString(16).padLeft(2, '0');
    final g = byte(color.g).toRadixString(16).padLeft(2, '0');
    final b = byte(color.b).toRadixString(16).padLeft(2, '0');
    return '#$r$g$b';
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final colors = _currentColors();
        final front = widget.front;
        final torso = _hex(front ? (colors['chest'] ?? BodyDiagram._neutral) : (colors['back'] ?? BodyDiagram._neutral));
        final shoulders = _hex(colors['shoulders'] ?? BodyDiagram._neutral);
        final core = _hex(colors['core'] ?? BodyDiagram._neutral);
        final arms = _hex(colors['arms'] ?? BodyDiagram._neutral);
        final legs = _hex(colors['legs'] ?? BodyDiagram._neutral);
        final neutral = _hex(BodyDiagram._neutral);
        final outline = _hex(_outline);

        final torsoOverlay = front
            ? 'M80,90 C96,98 144,98 160,90 L154,138 C140,150 100,150 86,138 Z'
            : 'M80,90 C96,98 144,98 160,90 L152,172 C138,182 102,182 88,172 Z';

        final decoration = front ? _frontLines : _backLines;

        final svg = '''
<svg viewBox="0 0 240 560" xmlns="http://www.w3.org/2000/svg">
  <path d="M72,88 C90,96 150,96 168,88 L160,140 C154,175 150,195 145,215 C158,225 156,245 152,255 L120,270 L88,255 C84,245 82,225 95,215 C90,195 86,175 80,140 Z" fill="$core" stroke="$outline" stroke-width="2"/>
  <path d="M152,258 C158,270 156,290 152,320 L144,420 C142,460 140,495 138,515 L126,515 C124,480 122,440 120,400 L120,300 C120,285 122,270 122,262 Z" fill="$legs" stroke="$outline" stroke-width="2"/>
  <path d="M88,258 C82,270 84,290 88,320 L96,420 C98,460 100,495 102,515 L114,515 C116,480 118,440 120,400 L120,300 C120,285 118,270 118,262 Z" fill="$legs" stroke="$outline" stroke-width="2"/>
  <circle cx="172" cy="96" r="25" fill="$shoulders" stroke="$outline" stroke-width="2"/>
  <circle cx="68" cy="96" r="25" fill="$shoulders" stroke="$outline" stroke-width="2"/>
  <path d="M172,92 C186,98 198,120 200,148 C202,178 196,206 190,228 L188,290 L168,286 L172,224 C168,196 166,164 168,136 C169,120 170,104 172,92 Z" fill="$arms" stroke="$outline" stroke-width="2"/>
  <path d="M68,92 C54,98 42,120 40,148 C38,178 44,206 50,228 L52,290 L72,286 L68,224 C72,196 74,164 72,136 C71,120 70,104 68,92 Z" fill="$arms" stroke="$outline" stroke-width="2"/>
  <path d="$torsoOverlay" fill="$torso" stroke="$outline" stroke-width="2"/>
  <path d="M110,70 C110,84 108,88 104,92 L106,96 C114,100 126,100 134,96 L136,92 C132,88 130,84 130,70 Z" fill="$neutral" stroke="$outline" stroke-width="2"/>
  <ellipse cx="120" cy="42" rx="25" ry="29" fill="$neutral" stroke="$outline" stroke-width="2"/>
  <g fill="none" stroke="$outline" stroke-width="1.4" stroke-linecap="round" opacity="0.75">
$decoration
  </g>
</svg>
''';

        return SvgPicture.string(svg, semanticsLabel: front ? 'Front body view' : 'Back body view');
      },
    );
  }

  static const _frontLines = '''
    <path d="M120,94 L120,146"/>
    <path d="M86,120 C100,132 140,132 154,120"/>
    <path d="M150,100 C158,108 160,118 158,128"/>
    <path d="M90,100 C82,108 80,118 82,128"/>
    <path d="M120,150 L120,252"/>
    <path d="M100,168 L140,168"/>
    <path d="M100,194 L140,194"/>
    <path d="M102,220 L138,220"/>
    <path d="M96,160 C88,190 88,220 96,248"/>
    <path d="M144,160 C152,190 152,220 144,248"/>
    <path d="M182,110 C186,150 184,190 178,222"/>
    <path d="M58,110 C54,150 56,190 62,222"/>
    <path d="M186,230 L182,286"/>
    <path d="M54,230 L58,286"/>
    <path d="M120,262 L120,500"/>
    <path d="M130,270 C136,330 138,400 136,440"/>
    <path d="M110,270 C104,330 102,400 104,440"/>
    <path d="M112,440 L146,440" opacity="0.5"/>
    <path d="M94,440 L128,440" opacity="0.5"/>
    <path d="M132,450 L136,510"/>
    <path d="M108,450 L104,510"/>
  ''';

  static const _backLines = '''
    <path d="M120,92 L150,120 L120,175 L90,120 Z"/>
    <path d="M120,175 L120,252"/>
    <path d="M92,100 C80,130 82,158 100,175"/>
    <path d="M148,100 C160,130 158,158 140,175"/>
    <path d="M150,100 C158,108 160,118 158,128"/>
    <path d="M90,100 C82,108 80,118 82,128"/>
    <path d="M104,190 L104,248"/>
    <path d="M136,190 L136,248"/>
    <path d="M182,110 C186,150 184,190 178,222"/>
    <path d="M58,110 C54,150 56,190 62,222"/>
    <path d="M186,230 L182,286"/>
    <path d="M54,230 L58,286"/>
    <path d="M96,262 C104,278 120,282 120,270"/>
    <path d="M144,262 C136,278 120,282 120,270"/>
    <path d="M120,262 L120,300"/>
    <path d="M120,300 L120,440"/>
    <path d="M130,308 C136,350 138,400 136,435"/>
    <path d="M110,308 C104,350 102,400 104,435"/>
    <path d="M112,450 L108,505"/>
    <path d="M128,450 L132,505"/>
    <path d="M120,450 L120,510"/>
  ''';
}
