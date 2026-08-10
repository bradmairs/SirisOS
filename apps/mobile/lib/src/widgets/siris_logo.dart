import 'dart:math' as math;

import 'package:flutter/material.dart';

/// SirisOS branding.
///
/// Uses the repository branding asset directly. The fallback is deliberately
/// visible so a missing/undecodable asset can never leave the logo area blank.
class SirisLogo extends StatefulWidget {
  const SirisLogo({
    this.size = 56,
    this.showWordmark = true,
    this.animate = true,
    super.key,
  });

  final double size;
  final bool showWordmark;

  /// Whether the thin ring around the S mark glistens. Disable for contexts
  /// where a continuous animation would be distracting (e.g. dense lists).
  final bool animate;

  static const _logoAsset = 'assets/branding/siris_logo_red.png';

  /// Intrinsic width/height ratio of [_logoAsset], so the widget can reserve
  /// exact space for it (needed to position the ring shimmer overlay).
  static const _assetAspectRatio = 310 / 385;

  // Ring geometry, fitted to the ring pixels in the source asset (robust
  // circle fit with outlier rejection against stray glow/spark pixels, not
  // eyeballed) so the shimmer overlay actually traces the printed ring.
  static const _ringCenterXFraction = 0.5028;
  static const _ringCenterYFraction = 0.4465;
  static const _ringRadiusXFraction = 0.4872;
  static const _ringRadiusYFraction = 0.3923;

  @override
  State<SirisLogo> createState() => _SirisLogoState();
}

class _SirisLogoState extends State<SirisLogo> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(seconds: 3));
    if (widget.animate) _controller.repeat();
  }

  @override
  void didUpdateWidget(covariant SirisLogo oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.animate && !oldWidget.animate) {
      _controller.repeat();
    } else if (!widget.animate && oldWidget.animate) {
      _controller.stop();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final width = widget.showWordmark ? widget.size * 2.25 : widget.size;
    final height = width / SirisLogo._assetAspectRatio;

    return Semantics(
      label: 'SirisOS',
      image: true,
      child: SizedBox(
        width: width,
        height: height,
        child: Stack(
          children: [
            Image.asset(
              SirisLogo._logoAsset,
              width: width,
              height: height,
              fit: BoxFit.fill,
              filterQuality: FilterQuality.high,
              gaplessPlayback: true,
              errorBuilder: (context, error, stackTrace) =>
                  _VisibleFallback(width: width, showWordmark: widget.showWordmark),
            ),
            if (widget.animate)
              Positioned.fill(
                child: IgnorePointer(
                  child: AnimatedBuilder(
                    animation: _controller,
                    builder: (context, _) => CustomPaint(
                      painter: _RingShimmerPainter(progress: _controller.value),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Paints a bright glint that sweeps around the S mark's ring, aligned to
/// the ring's measured position/shape in [SirisLogo._logoAsset].
class _RingShimmerPainter extends CustomPainter {
  const _RingShimmerPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(
      size.width * SirisLogo._ringCenterXFraction,
      size.height * SirisLogo._ringCenterYFraction,
    );
    final radiusX = size.width * SirisLogo._ringRadiusXFraction;
    final radiusY = size.height * SirisLogo._ringRadiusYFraction;
    final rect = Rect.fromCenter(center: center, width: radiusX * 2, height: radiusY * 2);
    final strokeWidth = size.width * 0.02;
    final angle = progress * 2 * math.pi;

    final gradient = SweepGradient(
      transform: GradientRotation(angle),
      colors: const [
        Colors.transparent,
        Colors.transparent,
        Color(0x00FFE9E9),
        Color(0xCCFFF3F3),
        Color(0x00FFE9E9),
        Colors.transparent,
        Colors.transparent,
      ],
      stops: const [0.0, 0.80, 0.885, 0.92, 0.955, 0.99, 1.0],
    );

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..shader = gradient.createShader(rect);

    canvas.drawOval(rect.deflate(strokeWidth / 2), paint);
  }

  @override
  bool shouldRepaint(covariant _RingShimmerPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _VisibleFallback extends StatelessWidget {
  const _VisibleFallback({required this.width, required this.showWordmark});

  final double width;
  final bool showWordmark;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: width,
          height: width,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFFFF2638), width: 2),
            boxShadow: const [
              BoxShadow(color: Color(0x66FF1027), blurRadius: 18),
            ],
          ),
          alignment: Alignment.center,
          child: Text(
            'S',
            style: TextStyle(
              color: const Color(0xFFFF2638),
              fontSize: width * .58,
              fontWeight: FontWeight.w900,
              fontStyle: FontStyle.italic,
              height: 1,
              shadows: const [Shadow(color: Color(0xFFFF1027), blurRadius: 12)],
            ),
          ),
        ),
        if (showWordmark) ...[
          const SizedBox(height: 8),
          Container(width: width * .62, height: 2, color: const Color(0xFFFF2638)),
          const SizedBox(height: 6),
          Text(
            'OS',
            style: TextStyle(
              color: const Color(0xFFE7E7EA),
              fontSize: width * .18,
              fontWeight: FontWeight.w700,
              letterSpacing: width * .025,
            ),
          ),
        ],
      ],
    );
  }
}
