package com.example.pet_project_frontend.core.navigation

import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pet_project_frontend.core.theme.MyPageColors

@Composable
fun BottomNavigation(
    currentRoute: String,
    onNavigate: (String) -> Unit = {}
) {
    NavigationBar(
        containerColor = androidx.compose.ui.graphics.Color.White
    ) {
        NavigationBarItem(
            selected = currentRoute == "petcare",
            onClick = { onNavigate("petcare") },
            icon = {
                Icon(
                    imageVector = Icons.Default.Favorite,
                    contentDescription = "펫케어",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "펫케어",
                    fontSize = 12.sp,
                    fontWeight = if (currentRoute == "petcare") FontWeight.SemiBold else FontWeight.Medium
                )
            },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MyPageColors.BottomBarActive,
                selectedTextColor = MyPageColors.BottomBarActive,
                unselectedIconColor = MyPageColors.BottomBarInactive,
                unselectedTextColor = MyPageColors.BottomBarInactive
            )
        )

        NavigationBarItem(
            selected = currentRoute == "map",
            onClick = { onNavigate("map") },
            icon = {
                Icon(
                    imageVector = Icons.Default.LocationOn,
                    contentDescription = "지도",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "지도",
                    fontSize = 12.sp,
                    fontWeight = if (currentRoute == "map") FontWeight.SemiBold else FontWeight.Medium
                )
            },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MyPageColors.BottomBarActive,
                selectedTextColor = MyPageColors.BottomBarActive,
                unselectedIconColor = MyPageColors.BottomBarInactive,
                unselectedTextColor = MyPageColors.BottomBarInactive
            )
        )

        NavigationBarItem(
            selected = currentRoute == "community",
            onClick = { onNavigate("community") },
            icon = {
                Icon(
                    imageVector = Icons.Default.Star,
                    contentDescription = "멍스타그램",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "멍스타그램",
                    fontSize = 12.sp,
                    fontWeight = if (currentRoute == "community") FontWeight.SemiBold else FontWeight.Medium
                )
            },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MyPageColors.BottomBarActive,
                selectedTextColor = MyPageColors.BottomBarActive,
                unselectedIconColor = MyPageColors.BottomBarInactive,
                unselectedTextColor = MyPageColors.BottomBarInactive
            )
        )

        NavigationBarItem(
            selected = currentRoute == "translator",
            onClick = { onNavigate("translator") },
            icon = {
                Icon(
                    imageVector = Icons.Default.Translate,
                    contentDescription = "번역기",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "번역기",
                    fontSize = 12.sp,
                    fontWeight = if (currentRoute == "translator") FontWeight.SemiBold else FontWeight.Medium
                )
            },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MyPageColors.BottomBarActive,
                selectedTextColor = MyPageColors.BottomBarActive,
                unselectedIconColor = MyPageColors.BottomBarInactive,
                unselectedTextColor = MyPageColors.BottomBarInactive
            )
        )

        NavigationBarItem(
            selected = currentRoute == "mypage",
            onClick = { onNavigate("mypage") },
            icon = {
                Icon(
                    imageVector = Icons.Default.PersonPin,
                    contentDescription = "마이페이지",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "마이페이지",
                    fontSize = 12.sp,
                    fontWeight = if (currentRoute == "mypage") FontWeight.SemiBold else FontWeight.Medium
                )
            },
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = MyPageColors.BottomBarActive,
                selectedTextColor = MyPageColors.BottomBarActive,
                unselectedIconColor = MyPageColors.BottomBarInactive,
                unselectedTextColor = MyPageColors.BottomBarInactive
            )
        )
    }
}