package com.example.pet_project_frontend.presentation.mypage.main.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.pet_project_frontend.core.theme.MyPageColors

@Composable
fun AppVersionSection() {
    Text(
        text = "앱 버전 2025.07.20",
        fontSize = 16.sp,
        fontWeight = FontWeight.Normal,
        color = MyPageColors.AppVersion,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
    )
}
