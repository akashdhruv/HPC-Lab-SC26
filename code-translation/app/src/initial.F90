! initial.F90 -- a perturbed square in the centre plus reproducible noise from an LCG.
subroutine initial(cfg)
   use kinds, only: rk, ik
   use config, only: config_t
   use grid, only: g
   implicit none
   type(config_t), intent(in) :: cfg

   integer :: i, j, i0, j0
   integer(ik) :: state
   real :: r

   state = int(cfg%seed, ik)
   i0 = g%nx/2
   j0 = g%ny/2
   do j = 1, g%ny
      do i = 1, g%nx
         if (abs(i-i0) <= 5 .and. abs(j-j0) <= 5) then
            g%u(i, j) = 0.5_rk
            g%v(i, j) = 0.25_rk
         end if
         state = mod(1103515245_ik*state+12345_ik, 2147483648_ik)
         r = real(state)/2147483648.0
         g%u(i, j) = g%u(i, j)-0.05_rk*r
         g%v(i, j) = g%v(i, j)+0.05_rk*r
      end do
   end do
end subroutine initial
