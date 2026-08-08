import 'package:flutter/material.dart';

import 'engineering_screen.dart';
import 'engineering_standards_screen.dart';
import 'sirishydro_screen.dart';

class EngineeringHubScreen extends StatelessWidget {
  const EngineeringHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const DefaultTabController(
      length: 3,
      child: Column(
        children: [
          Material(
            child: TabBar(
              tabs: [
                Tab(icon: Icon(Icons.calculate_rounded), text: 'Calculators'),
                Tab(icon: Icon(Icons.menu_book_rounded), text: 'Standards'),
                Tab(icon: Icon(Icons.water_drop_rounded), text: 'SirisHydro'),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                EngineeringScreen(),
                EngineeringStandardsScreen(),
                SirisHydroScreen(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
