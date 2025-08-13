package com.example.pet_project_frontend.presentation.mypage.main.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.pet_project_frontend.core.theme.MyPageColors

@Composable
fun ProfileInfoSection(  // 이름 변경
    name: String,
    birthDate: String,
    gender: String,
    breed: String,
    onNameClick: () -> Unit,
    onBirthdateClick: () -> Unit,
    onGenderClick: () -> Unit,
    onBreedClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 26.dp)
        ) {
            ProfileInfoItem(
                label = "이름",
                value = name,
                onClick = onNameClick
            )

            Divider(color = MyPageColors.Background)

            ProfileInfoItem(
                label = "생년월일",
                value = birthDate,
                onClick = onBirthdateClick
            )

            Divider(color = MyPageColors.Background)

            ProfileInfoItem(
                label = "성별",
                value = gender,
                onClick = onGenderClick
            )

            Divider(color = MyPageColors.Background)

            ProfileInfoItem(
                label = "견종",
                value = breed,
                onClick = onBreedClick
            )
        }
    }
}
