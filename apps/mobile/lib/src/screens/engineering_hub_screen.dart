import 'package:flutter/material.dart';

import 'engineering_screen.dart';
import 'engineering_standards_screen.dart';

class EngineeringHubScreen extends StatelessWidget {
  const EngineeringHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(
        children: const [
          Material(
            child: TabBar(
              tabs: [
                Tab(icon: Icon(Icons.calculate_rounded), text: 'Calculators'),
                Tab(icon: Icon(Icons.menu_book_rounded), text: 'Standards'),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                EngineeringScreen(),
                EngineeringStandardsScreen(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
