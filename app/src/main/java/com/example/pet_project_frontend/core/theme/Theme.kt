package com.example.pet_project_frontend.core.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    primary = MyPageColors.Primary,
    secondary = MyPageColors.Secondary,
    background = MyPageColors.Background
)

@Composable
fun PetCareTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        content = content
    )
}
